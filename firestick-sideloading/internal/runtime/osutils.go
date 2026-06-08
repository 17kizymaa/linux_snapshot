package runtime

import (
	"os"
	"os/exec"
	"strings"

	"github.com/anphuni/firestick-sideloading/internal/errors"
	"github.com/rs/zerolog"
)

// requiredPackages lists all Arch Linux packages needed for the Fire TV
// sideloading toolkit. The setup command checks and installs these.
var requiredPackages = []string{
	"android-tools",
	"android-udev",
	"scrcpy",
	"ffmpeg",
	"vlc",
	"usbutils",
}

// OSUtils provides Arch Linux system setup helpers: package detection,
// udev rules installation, group membership checks, and firewall verification.
// All commands use exec.Command with separate args -- never shell interpolation.
type OSUtils struct {
	logger zerolog.Logger
	dryRun bool
}

// NewOSUtils creates a new OSUtils with the given logger and dry-run mode.
// When dryRun is true, no changes are made to the system.
func NewOSUtils(logger zerolog.Logger, dryRun bool) *OSUtils {
	return &OSUtils{
		logger: logger,
		dryRun: dryRun,
	}
}

// IsPackageInstalled checks whether an Arch Linux package is installed
// by running `pacman -Q <pkg>`. Returns true if installed, false if not.
func (u *OSUtils) IsPackageInstalled(pkg string) (bool, error) {
	cmd := exec.Command("pacman", "-Q", pkg)
	err := cmd.Run()
	if err != nil {
		// Non-zero exit means package is not installed -- not an error
		return false, nil
	}
	return true, nil
}

// InstallPackages installs the given packages via `sudo pacman -S`.
// When dryRun is true, only logs what would be done.
func (u *OSUtils) InstallPackages(pkgs []string) error {
	args := append([]string{"pacman", "-S", "--noconfirm", "--needed"}, pkgs...)

	if u.dryRun {
		u.logger.Info().Strs("packages", pkgs).Msg("[dry-run] Would run: sudo " + strings.Join(args, " "))
		return nil
	}

	u.logger.Info().Strs("packages", pkgs).Msg("Installing packages via pacman")

	cmd := exec.Command("sudo", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return errors.NewError(errors.PermissionError,
			"Package installation failed. Try running with sudo.", err)
	}
	return nil
}

// udevRulesContent is the content written to /etc/udev/rules.d/51-android.rules.
// Includes Amazon (1949) and standard Android vendor IDs.
const udevRulesContent = `# Amazon Fire TV devices
SUBSYSTEM=="usb", ATTR{idVendor}=="1949", MODE="0666", GROUP="adbusers", TAG+="uaccess"

# Google / Android
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="adbusers", TAG+="uaccess"

# HTC
SUBSYSTEM=="usb", ATTR{idVendor}=="0bb4", MODE="0666", GROUP="adbusers", TAG+="uaccess"

# Samsung
SUBSYSTEM=="usb", ATTR{idVendor}=="04e8", MODE="0666", GROUP="adbusers", TAG+="uaccess"

# Motorola
SUBSYSTEM=="usb", ATTR{idVendor}=="22b8", MODE="0666", GROUP="adbusers", TAG+="uaccess"

# LG
SUBSYSTEM=="usb", ATTR{idVendor}=="1004", MODE="0666", GROUP="adbusers", TAG+="uaccess"

# Huawei
SUBSYSTEM=="usb", ATTR{idVendor}=="12d1", MODE="0666", GROUP="adbusers", TAG+="uaccess"

# Sony
SUBSYSTEM=="usb", ATTR{idVendor}=="0fce", MODE="0666", GROUP="adbusers", TAG+="uaccess"

# OnePlus
SUBSYSTEM=="usb", ATTR{idVendor}=="2a70", MODE="0666", GROUP="adbusers", TAG+="uaccess"
`

// udevRulesPath is the standard location for Android udev rules on Arch Linux.
const udevRulesPath = "/etc/udev/rules.d/51-android.rules"

// InstallUdevRules writes the Amazon + Android udev rules file and reloads udev.
// When dryRun is true, only logs what would be done.
func (u *OSUtils) InstallUdevRules() error {
	if u.dryRun {
		u.logger.Info().Msg("[dry-run] Would write udev rules to " + udevRulesPath + " and reload")
		return nil
	}

	u.logger.Info().Msg("Writing udev rules to " + udevRulesPath)

	// Write the rules file
	if err := os.WriteFile(udevRulesPath, []byte(udevRulesContent), 0644); err != nil {
		return errors.NewError(errors.PermissionError,
			"Failed to write udev rules. Run: sudo firetv setup", err)
	}

	// Reload udev rules
	cmd := exec.Command("sudo", "udevadm", "control", "--reload-rules")
	if err := cmd.Run(); err != nil {
		return errors.NewError(errors.PermissionError,
			"Failed to reload udev rules.", err)
	}

	// Trigger udev to apply new rules
	cmd = exec.Command("sudo", "udevadm", "trigger")
	if err := cmd.Run(); err != nil {
		u.logger.Warn().Err(err).Msg("udevadm trigger failed (non-fatal)")
	}

	return nil
}

// UdevRulesExist checks whether the udev rules file is already present.
func (u *OSUtils) UdevRulesExist() bool {
	_, err := os.Stat(udevRulesPath)
	return err == nil
}

// CheckGroupMembership checks whether the current user is in the given group
// by running `groups` and searching the output.
func (u *OSUtils) CheckGroupMembership(group string) (bool, error) {
	cmd := exec.Command("groups")
	out, err := cmd.Output()
	if err != nil {
		return false, errors.NewError(errors.PermissionError,
			"Failed to check group membership", err)
	}

	groups := strings.Fields(string(out))
	for _, g := range groups {
		if g == group {
			return true, nil
		}
	}
	return false, nil
}

// CheckFirewall checks whether a firewall (ufw or firewalld) is active
// and whether it might block ADB traffic on port 5555.
// This is informational only -- not blocking.
func (u *OSUtils) CheckFirewall() (bool, error) {
	// Check if firewalld is active
	cmd := exec.Command("systemctl", "is-active", "firewalld")
	out, err := cmd.Output()
	if err == nil && strings.TrimSpace(string(out)) == "active" {
		u.logger.Info().Msg("firewalld is active. Ensure port 5555/tcp is allowed for ADB over network.")
		return false, nil
	}

	// Check if ufw is active
	cmd = exec.Command("ufw", "status")
	out, err = cmd.Output()
	if err == nil && strings.Contains(string(out), "Status: active") {
		u.logger.Info().Msg("ufw is active. Ensure port 5555/tcp is allowed for ADB over network.")
		return false, nil
	}

	return true, nil
}

// SetupVerification holds the results of a full system verification.
type SetupVerification struct {
	PackagesInstalled []string `json:"packages_installed"`
	PackagesMissing   []string `json:"packages_missing"`
	UdevRulesOk       bool     `json:"udev_rules_ok"`
	InAdbusersGroup   bool     `json:"in_adbusers_group"`
	FirewallOk        bool     `json:"firewall_ok"`
	NeedsReboot       bool     `json:"needs_reboot"`
}

// RunVerification performs a full system verification and returns
// a SetupVerification struct with all check results.
func (u *OSUtils) RunVerification() (*SetupVerification, error) {
	result := &SetupVerification{}

	// Check all required packages
	for _, pkg := range requiredPackages {
		installed, err := u.IsPackageInstalled(pkg)
		if err != nil {
			u.logger.Warn().Str("package", pkg).Err(err).Msg("could not check package")
			result.PackagesMissing = append(result.PackagesMissing, pkg)
			continue
		}
		if installed {
			result.PackagesInstalled = append(result.PackagesInstalled, pkg)
		} else {
			result.PackagesMissing = append(result.PackagesMissing, pkg)
		}
	}

	// Check udev rules
	result.UdevRulesOk = u.UdevRulesExist()

	// Check group membership
	inGroup, err := u.CheckGroupMembership("adbusers")
	if err != nil {
		u.logger.Warn().Err(err).Msg("could not check adbusers group")
	}
	result.InAdbusersGroup = inGroup

	// Check firewall
	fwOk, err := u.CheckFirewall()
	if err != nil {
		u.logger.Warn().Err(err).Msg("could not check firewall")
	}
	result.FirewallOk = fwOk

	// Determine if reboot is needed (group change requires re-login)
	if !result.InAdbusersGroup {
		result.NeedsReboot = true
	}

	return result, nil
}

