package errors

import (
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestExitCodeConnectionError(t *testing.T) {
	assert.Equal(t, 1, ExitCode(ConnectionError))
}

func TestExitCodeAuthError(t *testing.T) {
	assert.Equal(t, 1, ExitCode(AuthError))
}

func TestExitCodeDeviceOfflineError(t *testing.T) {
	assert.Equal(t, 2, ExitCode(DeviceOfflineError))
}

func TestExitCodeNotFoundError(t *testing.T) {
	assert.Equal(t, 1, ExitCode(NotFoundError))
}

func TestExitCodePermissionError(t *testing.T) {
	assert.Equal(t, 3, ExitCode(PermissionError))
}

func TestExitCodeADBServerError(t *testing.T) {
	assert.Equal(t, 3, ExitCode(ADBServerError))
}

func TestRecoveryNonEmpty(t *testing.T) {
	types := []ErrorType{
		ConnectionError,
		AuthError,
		DeviceOfflineError,
		NotFoundError,
		PermissionError,
		ADBServerError,
		InstallError,
	}
	for _, et := range types {
		t.Run(string(et), func(t *testing.T) {
			assert.NotEmpty(t, Recovery(et), "Recovery() must return non-empty for %s", et)
		})
	}
}

func TestClassifiedErrorError(t *testing.T) {
	err := NewError(ConnectionError, "test message", nil)
	assert.Contains(t, err.Error(), string(ConnectionError))
	assert.Contains(t, err.Error(), "test message")
}

func TestClassifiedErrorUnwrap(t *testing.T) {
	inner := errors.New("inner error")
	err := NewError(ConnectionError, "outer", inner)
	assert.True(t, errors.Is(err, inner))
}

func TestNewErrorSetsExitCode(t *testing.T) {
	err := NewError(DeviceOfflineError, "offline", nil)
	assert.Equal(t, 2, err.ExitCode)
}
