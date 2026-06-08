package runtime

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
	"time"

	"github.com/anphuni/firestick-sideloading/internal/errors"
	"github.com/rs/zerolog"
)

// DeviceState represents the connection state of an ADB device.
type DeviceState string

const (
	StateDevice        DeviceState = "device"
	StateOffline       DeviceState = "offline"
	StateUnauthorized  DeviceState = "unauthorized"
)

// ADBRunner executes adb commands with timeout, logging, and error classification.
// All ADB commands use exec.Command with separate args -- NEVER shell out via
// system() or string interpolation for user input. The serial value is passed
// as a separate -s flag argument.
//
// Safety note: Binding verification to 127.0.0.1 is enforced by relying on ADB's
// default behavior when no -a flag is passed. The tool never starts a server on
// 0.0.0.0.
type ADBRunner struct {
	timeout time.Duration
	logger  zerolog.Logger
	serial  string
}

// NewADBRunner creates a new ADBRunner with the given timeout and logger.
func NewADBRunner(timeout time.Duration, logger zerolog.Logger) *ADBRunner {
	return &ADBRunner{
		timeout: timeout,
		logger:  logger,
	}
}

// Run executes an adb command with the runner's timeout.
// If serial is set, prepends -s <serial> to args.
func (r *ADBRunner) Run(ctx context.Context, args ...string) (string, error) {
	if r.serial != "" {
		args = append([]string{"-s", r.serial}, args...)
	}

	ctx, cancel := context.WithTimeout(ctx, r.timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "adb", args...)
	r.logger.Debug().Strs("args", args).Msg("adb command")

	out, err := cmd.CombinedOutput()
	if err != nil {
		output := string(out)
		r.logger.Error().Err(err).Str("output", output).Strs("args", args).Msg("adb command failed")

		errType := errors.ADBServerError
		if strings.Contains(output, "device offline") || strings.Contains(output, "error: device offline") {
			errType = errors.DeviceOfflineError
		} else if strings.Contains(output, "device not found") {
			errType = errors.NotFoundError
		} else if strings.Contains(output, "no devices/emulators found") {
			errType = errors.NotFoundError
		} else if strings.Contains(output, "unauthorized") {
			errType = errors.AuthError
		} else if strings.Contains(output, "could not install *smartsocket") || strings.Contains(output, "Address already in use") {
			errType = errors.ADBServerError
		} else if strings.Contains(output, "Connection refused") || strings.Contains(output, "No route to host") {
			errType = errors.ConnectionError
		}

		return "", errors.NewError(errType, fmt.Sprintf("adb %s failed", strings.Join(args, " ")), err)
	}

	return string(out), nil
}

// RunWithTimeout executes an adb command with a specific timeout.
func (r *ADBRunner) RunWithTimeout(ctx context.Context, timeout time.Duration, args ...string) (string, error) {
	subCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	return r.Run(subCtx, args...)
}

// EnsureServer starts the ADB server (idempotent) and verifies binding.
func (r *ADBRunner) EnsureServer(ctx context.Context) error {
	r.logger.Info().Msg("ensuring ADB server is running")

	if _, err := r.Run(ctx, "start-server"); err != nil {
		return errors.NewError(errors.ADBServerError, "failed to start ADB server", err)
	}

	return r.VerifyBinding(ctx)
}

// VerifyBinding confirms the ADB server is responsive.
func (r *ADBRunner) VerifyBinding(ctx context.Context) error {
	r.logger.Debug().Msg("verifying ADB server binding")

	out, err := r.Run(ctx, "shell", "echo", "binding_test")
	if err != nil {
		return errors.NewError(errors.ADBServerError, "ADB server not responsive", err)
	}

	if !strings.Contains(out, "binding_test") {
		return errors.NewError(errors.ADBServerError, "ADB server returned unexpected output", nil)
	}

	r.logger.Info().Msg("ADB server verified on 127.0.0.1")
	return nil
}

// ForSerial returns a new ADBRunner scoped to the given serial.
func (r *ADBRunner) ForSerial(serial string) *ADBRunner {
	return &ADBRunner{
		timeout: r.timeout,
		logger:  r.logger,
		serial:  serial,
	}
}

// GetDeviceState returns the state of a device by serial.
func (r *ADBRunner) GetDeviceState(serial string) (DeviceState, error) {
	out, err := r.Run(context.Background(), "devices", "-l")
	if err != nil {
		return "", err
	}

	lines := strings.Split(out, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "List of devices") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) >= 2 && fields[0] == serial {
			return DeviceState(fields[1]), nil
		}
	}

	return "", errors.NewError(errors.NotFoundError, fmt.Sprintf("device %s not found in adb devices", serial), nil)
}
