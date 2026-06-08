package device

import (
	"strings"
	"testing"

	"github.com/anphuni/firestick-sideloading/pkg/proto"
	"github.com/stretchr/testify/assert"
)

func TestParseDeviceLine_NormalDevice(t *testing.T) {
	line := "192.168.1.50:5555\tdevice product:bramble model:Redmi device:missha"
	result := parseDeviceLine(line)
	assert.NotNil(t, result)
	assert.Equal(t, "192.168.1.50:5555", result.Serial)
	assert.Equal(t, "device", result.State)
	assert.Equal(t, "Redmi", result.Model)
	assert.Equal(t, string(proto.ConnectionNetwork), result.ConnectionType)
}

func TestParseDeviceLine_OfflineDevice(t *testing.T) {
	line := "192.168.1.50:5555\toffline"
	result := parseDeviceLine(line)
	assert.NotNil(t, result)
	assert.Equal(t, "192.168.1.50:5555", result.Serial)
	assert.Equal(t, "offline", result.State)
	assert.Equal(t, "", result.Model)
}

func TestParseDeviceLine_Unauthorized(t *testing.T) {
	line := "192.168.1.50:5555\tunauthorized"
	result := parseDeviceLine(line)
	assert.NotNil(t, result)
	assert.Equal(t, "192.168.1.50:5555", result.Serial)
	assert.Equal(t, "unauthorized", result.State)
}

func TestParseDeviceLine_USBDevice(t *testing.T) {
	line := "ABCD1234\tdevice usb:1-2 product:bramble model:FireTV device:missha"
	result := parseDeviceLine(line)
	assert.NotNil(t, result)
	assert.Equal(t, "ABCD1234", result.Serial)
	assert.Equal(t, "device", result.State)
	assert.Equal(t, "FireTV", result.Model)
	assert.Equal(t, string(proto.ConnectionUSB), result.ConnectionType)
}

func TestParseDeviceLine_NetworkByColon(t *testing.T) {
	line := "192.168.1.50:5555\tdevice product:bramble model:AFTMM device:missha"
	result := parseDeviceLine(line)
	assert.NotNil(t, result)
	assert.Equal(t, string(proto.ConnectionNetwork), result.ConnectionType)
}

func TestParseDeviceLine_EmptyLine(t *testing.T) {
	result := parseDeviceLine("")
	assert.Nil(t, result)
}

func TestParseDeviceLine_HeaderLine(t *testing.T) {
	result := parseDeviceLine("List of devices attached")
	assert.Nil(t, result)
}

func TestParseDevicesOutput_Empty(t *testing.T) {
	output := "List of devices attached\n"
	devices := parseDevicesOutput(output)
	assert.Empty(t, devices)
}

func TestParseDevicesOutput_MultipleDevices(t *testing.T) {
	output := strings.Join([]string{
		"List of devices attached",
		"192.168.1.50:5555\tdevice product:bramble model:AFTMM device:missha",
		"ABCD1234\tdevice usb:1-2 product:bramble model:FireTV device:missha",
		"192.168.1.51:5555\toffline",
	}, "\n")
	devices := parseDevicesOutput(output)
	assert.Len(t, devices, 3)
	assert.Equal(t, "192.168.1.50:5555", devices[0].Serial)
	assert.Equal(t, "ABCD1234", devices[1].Serial)
	assert.Equal(t, "offline", devices[2].State)
}

func TestParseDevicesOutput_FilterEmptyModel(t *testing.T) {
	// Devices with empty model and no colon in serial should be filtered
	output := strings.Join([]string{
		"List of devices attached",
		"192.168.1.50:5555\tdevice product:bramble model:AFTMM device:missha",
		"some_serial\tdevice usb:1-2 product:bramble device:missha",
	}, "\n")
	devices := parseDevicesOutput(output)
	// The network device should be kept (has colon in serial)
	// The USB device with empty model should be filtered
	assert.Len(t, devices, 1)
	assert.Equal(t, "192.168.1.50:5555", devices[0].Serial)
}

func TestParseDevicesOutput_SingleDevice(t *testing.T) {
	output := strings.Join([]string{
		"List of devices attached",
		"192.168.1.50:5555\tdevice product:bramble model:AFTMM device:missha",
	}, "\n")
	devices := parseDevicesOutput(output)
	assert.Len(t, devices, 1)
	assert.Equal(t, "AFTMM", devices[0].Model)
	assert.Equal(t, string(proto.ConnectionNetwork), devices[0].ConnectionType)
}
