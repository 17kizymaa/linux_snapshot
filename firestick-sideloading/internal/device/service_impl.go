package device

import (
	"context"
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
