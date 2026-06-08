package proto

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestDeviceInfoFields(t *testing.T) {
	d := DeviceInfo{
		Serial:         "192.168.1.50:5555",
		Model:          "AFTMM",
		State:          "device",
		ConnectionType: "network",
		FireOSVersion:  "Fire OS 7.6.8.1",
		SDKLevel:       "28",
		Manufacturer:   "Amazon",
	}
	assert.Equal(t, "192.168.1.50:5555", d.Serial)
	assert.Equal(t, "AFTMM", d.Model)
	assert.Equal(t, "device", d.State)
	assert.Equal(t, "network", d.ConnectionType)
	assert.Equal(t, "Fire OS 7.6.8.1", d.FireOSVersion)
	assert.Equal(t, "28", d.SDKLevel)
	assert.Equal(t, "Amazon", d.Manufacturer)
}

func TestConnectionStateConstants(t *testing.T) {
	assert.Equal(t, ConnectionState("usb"), ConnectionUSB)
	assert.Equal(t, ConnectionState("network"), ConnectionNetwork)
	assert.Equal(t, ConnectionState("unknown"), ConnectionUnknown)
}

func TestDeviceFilterFields(t *testing.T) {
	f := DeviceFilter{
		BySerial:   "192.168.1.50:5555",
		ByState:    "device",
		OnlyFireTV: true,
	}
	assert.Equal(t, "192.168.1.50:5555", f.BySerial)
	assert.Equal(t, "device", f.ByState)
	assert.True(t, f.OnlyFireTV)
}
