package device

import (
	"context"
	"fmt"
	"strings"

	"github.com/anphuni/firestick-sideloading/internal/errors"
	"github.com/anphuni/firestick-sideloading/internal/runtime"
	"github.com/anphuni/firestick-sideloading/pkg/proto"
	"github.com/rs/zerolog"
)

// deviceService is the ADB-based implementation of DeviceService.
type deviceService struct {
	runner *runtime.ADBRunner
	logger zerolog.Logger
}

// NewDeviceService creates a new deviceService with the given ADB runner and logger.
func NewDeviceService(runner *runtime.ADBRunner, logger zerolog.Logger) *deviceService {
	return &deviceService{
		runner: runner,
		logger: logger,
	}
}

// Detect runs `adb devices -l` and parses the output into a slice of DeviceInfo.
func (s *deviceService) Detect(ctx context.Context) ([]proto.DeviceInfo, error) {
	s.logger.Debug().Msg("detecting devices via adb devices -l")

	out, err := s.runner.Run(ctx, "devices", "-l")
	if err != nil {
		return nil, errors.NewError(errors.ADBServerError, "failed to list ADB devices", err)
	}

	devices := parseDevicesOutput(out)
	s.logger.Info().Int("count", len(devices)).Msg("device detection complete")
	return devices, nil
}

// List delegates to Detect.
func (s *deviceService) List(ctx context.Context) ([]proto.DeviceInfo, error) {
	return s.Detect(ctx)
}

// Connect establishes a network ADB connection to the target IP or serial.
func (s *deviceService) Connect(ctx context.Context, target string) error {
	// Append :5555 if target is a bare IP (no port)
	target = ensurePort(target)

	s.logger.Info().Str("target", target).Msg("connecting to device")

	out, err := s.runner.Run(ctx, "connect", target)
	if err != nil {
		return errors.NewError(errors.ConnectionError, fmt.Sprintf("failed to connect to %s: %s", target, out), err)
	}

	output := strings.TrimSpace(out)

	if strings.HasPrefix(output, "connected to") || strings.HasPrefix(output, "already connected to") {
		s.logger.Info().Str("target", target).Msg("connection command succeeded, verifying state")

		// Verify device state after connect
		return s.verifyConnectState(ctx, target)
	}

	if strings.Contains(output, "failed to connect") || strings.Contains(output, "Connection refused") {
		return errors.NewError(errors.ConnectionError, fmt.Sprintf("failed to connect to %s: %s", target, output), nil)
	}

	// Unknown output -- treat as connection failure
	return errors.NewError(errors.ConnectionError, fmt.Sprintf("unexpected connect response: %s", output), nil)
}

// verifyConnectState checks adb devices after connecting and detects unauthorized/offline.
func (s *deviceService) verifyConnectState(ctx context.Context, target string) error {
	out, err := s.runner.Run(ctx, "devices", "-l")
	if err != nil {
		// Non-fatal: the connect itself succeeded
		s.logger.Warn().Err(err).Msg("could not verify post-connect device state")
		return nil
	}

	devices := parseDevicesOutput(out)
	for _, d := range devices {
		if d.Serial == target || strings.HasPrefix(d.Serial, target) {
			switch d.State {
			case "unauthorized":
				return errors.NewError(errors.AuthError,
					"RSA authorization required. Check your Fire TV screen and tap Allow for the ADB debugging prompt.", nil)
			case "offline":
				return errors.NewError(errors.DeviceOfflineError,
					"Device went offline after connect. It may be asleep or on a different network.", nil)
			}
		}
	}

	return nil
}

// ensurePort appends :5555 to a bare IP address if no port is present.
func ensurePort(target string) string {
	if strings.Contains(target, ":") {
		return target
	}
	return target + ":5555"
}

// Info retrieves enriched device properties via adb shell getprop.
func (s *deviceService) Info(ctx context.Context, serial string) (*proto.DeviceInfo, error) {
	s.logger.Debug().Str("serial", serial).Msg("getting device info via getprop")

	// Create a device-scoped runner
	scopedRunner := s.runner.ForSerial(serial)

	info := &proto.DeviceInfo{
		Serial: serial,
	}

	// Run getprop for each property
	model, err := scopedRunner.Run(ctx, "shell", "getprop", "ro.product.model")
	if err != nil {
		s.logger.Warn().Err(err).Msg("failed to get ro.product.model")
		info.Model = "unknown"
	} else {
		info.Model = deflateProp(model)
	}

	sdk, err := scopedRunner.Run(ctx, "shell", "getprop", "ro.build.version.sdk")
	if err != nil {
		s.logger.Warn().Err(err).Msg("failed to get ro.build.version.sdk")
		info.SDKLevel = "unknown"
	} else {
		info.SDKLevel = deflateProp(sdk)
	}

	fireOS, err := scopedRunner.Run(ctx, "shell", "getprop", "ro.build.display.id")
	if err != nil {
		s.logger.Warn().Err(err).Msg("failed to get ro.build.display.id")
		info.FireOSVersion = "unknown"
	} else {
		info.FireOSVersion = deflateProp(fireOS)
	}

	manufacturer, err := scopedRunner.Run(ctx, "shell", "getprop", "ro.product.manufacturer")
	if err != nil {
		s.logger.Warn().Err(err).Msg("failed to get ro.product.manufacturer")
		info.Manufacturer = "unknown"
	} else {
		info.Manufacturer = deflateProp(manufacturer)
	}

	s.logger.Info().Str("model", info.Model).Str("serial", serial).Msg("device info retrieved")
	return info, nil
}

// deflateProp trims whitespace and returns "unknown" for empty values.
func deflateProp(raw string) string {
	v := strings.TrimSpace(raw)
	if v == "" {
		return "unknown"
	}
	return v
}

// HealthCheck verifies device responsiveness via echo ping.
func (s *deviceService) HealthCheck(ctx context.Context, serial string) error {
	s.logger.Debug().Str("serial", serial).Msg("running health check (echo ping)")

	scopedRunner := s.runner.ForSerial(serial)

	out, err := scopedRunner.Run(ctx, "shell", "echo", "firetv_ping")
	if err != nil {
		// Check device state to classify the error
		state, stateErr := s.runner.GetDeviceState(serial)
		if stateErr == nil {
			switch state {
			case runtime.StateOffline:
				return errors.NewError(errors.DeviceOfflineError,
					"Device is offline. It may be asleep. Wake it and retry.", nil)
			case runtime.StateUnauthorized:
				return errors.NewError(errors.AuthError,
					"Device authorization lost. Re-authorize and retry.", nil)
			}
		}
		return errors.NewError(errors.ConnectionError,
			fmt.Sprintf("Device health check failed: %v", err), err)
	}

	if strings.Contains(out, "firetv_ping") {
		s.logger.Debug().Str("serial", serial).Msg("health check passed")
		return nil
	}

	return errors.NewError(errors.ConnectionError,
		"Device health check returned unexpected output", nil)
}

// Disconnect cleanly disconnects from the target and verifies.
func (s *deviceService) Disconnect(ctx context.Context, target string) error {
	s.logger.Info().Str("target", target).Msg("disconnecting from device")

	out, err := s.runner.Run(ctx, "disconnect", target)
	if err != nil {
		return errors.NewError(errors.ConnectionError,
			fmt.Sprintf("failed to disconnect from %s: %v", target, err), err)
	}

	_ = out // adb disconnect returns empty output on success

	// Verify: run adb devices and confirm target no longer appears
	devicesOut, err := s.runner.Run(ctx, "devices")
	if err != nil {
		s.logger.Warn().Err(err).Msg("could not verify disconnection")
		return nil
	}

	lines := strings.Split(devicesOut, "\n")
	for _, line := range lines {
		fields := strings.Fields(line)
		if len(fields) >= 1 && (fields[0] == target || strings.HasPrefix(fields[0], target)) {
			// Device still shows up -- might be a different transport
			s.logger.Warn().Str("target", target).Msg("device still in adb devices after disconnect")
			return nil
		}
	}

	s.logger.Info().Str("target", target).Msg("disconnection verified")
	return nil
}

// parseDevicesOutput parses the raw output of `adb devices -l` into DeviceInfo slice.
func parseDevicesOutput(output string) []proto.DeviceInfo {
	var devices []proto.DeviceInfo
	lines := strings.Split(output, "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)
		device := parseDeviceLine(line)
		if device == nil {
			continue
		}
		devices = append(devices, *device)
	}

	return devices
}

// parseDeviceLine parses a single line from `adb devices -l` output.
// Returns nil for header lines, empty lines, or lines that should be filtered.
func parseDeviceLine(line string) *proto.DeviceInfo {
	if line == "" || strings.HasPrefix(line, "List of devices") {
		return nil
	}

	fields := strings.Fields(line)
	if len(fields) < 2 {
		return nil
	}

	serial := fields[0]
	state := ""

	// Find the state field: look for "device", "offline", or "unauthorized"
	for _, f := range fields[1:] {
		if f == "device" || f == "offline" || f == "unauthorized" {
			state = f
			break
		}
	}

	if state == "" {
		return nil
	}

	info := &proto.DeviceInfo{
		Serial: serial,
		State:  state,
	}

	// Parse connection type from the full line
	if strings.Contains(line, "usb:") {
		info.ConnectionType = string(proto.ConnectionUSB)
	} else if strings.Contains(serial, ":") {
		// Network device: serial contains IP:port
		info.ConnectionType = string(proto.ConnectionNetwork)
	} else {
		info.ConnectionType = string(proto.ConnectionUnknown)
	}

	// Parse model from "model:" tag
	for _, f := range fields {
		if strings.HasPrefix(f, "model:") {
			info.Model = strings.TrimPrefix(f, "model:")
			break
		}
	}

	// Filter: only include devices with a model or network connection
	// (network devices may not show model in adb devices -l)
	if info.Model == "" && info.ConnectionType != string(proto.ConnectionNetwork) {
		return nil
	}

	return info
}
