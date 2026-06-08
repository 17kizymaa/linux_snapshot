package errors

import "fmt"

// ErrorType classifies errors for recovery suggestions and exit codes.
type ErrorType string

const (
	ConnectionError    ErrorType = "connection"
	AuthError          ErrorType = "auth"
	DeviceOfflineError ErrorType = "device-offline"
	NotFoundError      ErrorType = "not-found"
	PermissionError    ErrorType = "permission"
	ADBServerError     ErrorType = "adb-server"
	InstallError       ErrorType = "install"
)

// ClassifiedError wraps an error with type classification, exit code, and recovery hint.
type ClassifiedError struct {
	Type     ErrorType
	Message  string
	Err      error
	ExitCode int
}

// Error implements the error interface.
func (e *ClassifiedError) Error() string {
	return fmt.Sprintf("%s: %s", e.Type, e.Message)
}

// Unwrap returns the underlying wrapped error.
func (e *ClassifiedError) Unwrap() error {
	return e.Err
}

// ExitCode returns the exit code for a given ErrorType.
func ExitCode(et ErrorType) int {
	switch et {
	case ConnectionError, AuthError, NotFoundError, InstallError:
		return 1
	case DeviceOfflineError:
		return 2
	case PermissionError, ADBServerError:
		return 3
	default:
		return 1
	}
}

// Recovery returns a human-readable recovery suggestion for the error type.
func Recovery(et ErrorType) string {
	switch et {
	case ConnectionError:
		return "Check the device IP and ensure it's on the same network. Run: firetv connect <IP> --force"
	case AuthError:
		return "Check your Fire TV screen for an RSA authorization prompt. Run: firetv connect <IP> --timeout 60s"
	case DeviceOfflineError:
		return "Device may be asleep. Wake it and retry. Run: adb wait-for-device && firetv status"
	case NotFoundError:
		return "Device not found in ADB device list. Run: adb devices -l"
	case PermissionError:
		return "Missing system permissions. Run: firetv setup"
	case ADBServerError:
		return "ADB server conflict. Run: adb kill-server && firetv status"
	case InstallError:
		return "Installation failed. Check APK integrity and device storage. Run: adb shell df /data"
	default:
		return "Unknown error. Run: firetv status for diagnostics"
	}
}

// NewError constructs a ClassifiedError with auto-set ExitCode.
func NewError(errType ErrorType, msg string, err error) *ClassifiedError {
	return &ClassifiedError{
		Type:     errType,
		Message:  msg,
		Err:      err,
		ExitCode: ExitCode(errType),
	}
}
