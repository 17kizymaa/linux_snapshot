package runtime

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestIsPackageInstalled_Installed(t *testing.T) {
	logger := zerolog.New(nil)
	osu := NewOSUtils(logger, true)

	// ffmpeg may or may not be installed -- just verify no error
	_, err := osu.IsPackageInstalled("ffmpeg")
	assert.NoError(t, err)
}

func TestIsPackageInstalled_Nonexistent(t *testing.T) {
	logger := zerolog.New(nil)
	osu := NewOSUtils(logger, true)

	installed, err := osu.IsPackageInstalled("nonexistent-package-xyz123")
	assert.NoError(t, err)
	assert.False(t, installed)
}

func TestInstallPackages_DryRun(t *testing.T) {
	logger := zerolog.New(nil)
	osu := NewOSUtils(logger, true)

	err := osu.InstallPackages([]string{"android-tools", "android-udev"})
	assert.NoError(t, err) // dry-run should not fail
}

func TestInstallUdevRules_DryRun(t *testing.T) {
	logger := zerolog.New(nil)
	osu := NewOSUtils(logger, true)

	err := osu.InstallUdevRules()
	assert.NoError(t, err) // dry-run should not fail
}

func TestCheckGroupMembership_CurrentUser(t *testing.T) {
	logger := zerolog.New(nil)
	osu := NewOSUtils(logger, true)

	// "root" group should always exist
	inGroup, err := osu.CheckGroupMembership("root")
	assert.NoError(t, err)
	// We can't assert true/false without knowing the system
	_ = inGroup
}

func TestCheckGroupMembership_Nonexistent(t *testing.T) {
	logger := zerolog.New(nil)
	osu := NewOSUtils(logger, true)

	inGroup, err := osu.CheckGroupMembership("nonexistent-group-xyz123")
	assert.NoError(t, err)
	assert.False(t, inGroup)
}

func TestRunVerification(t *testing.T) {
	logger := zerolog.New(nil)
	osu := NewOSUtils(logger, true)

	result, err := osu.RunVerification()
	assert.NoError(t, err)
	assert.NotNil(t, result)
	// Verify that all required packages are checked
	total := len(result.PackagesInstalled) + len(result.PackagesMissing)
	assert.Greater(t, total, 0)
}

func TestNewOSUtils(t *testing.T) {
	logger := zerolog.New(nil)
	osu := NewOSUtils(logger, false)
	assert.NotNil(t, osu)
	assert.False(t, osu.dryRun)

	osuDry := NewOSUtils(logger, true)
	assert.True(t, osuDry.dryRun)
}

func TestCheckFirewall(t *testing.T) {
	logger := zerolog.New(nil)
	osu := NewOSUtils(logger, true)

	ok, err := osu.CheckFirewall()
	assert.NoError(t, err)
	// Informational only -- just verify it runs
	_ = ok
}
