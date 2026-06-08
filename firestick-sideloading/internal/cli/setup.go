package cli

import (
	"fmt"
	"os"

	"github.com/anphuni/firestick-sideloading/internal/errors"
	"github.com/anphuni/firestick-sideloading/internal/runtime"
	"github.com/rs/zerolog"
	"github.com/spf13/cobra"
)

var (
	setupDryRun  bool
	setupSystemd bool
)

var setupCmd = &cobra.Command{
	Use:   "setup",
	Short: "Arch Linux one-time setup helper",
	Long:  "Installs required packages, configures udev rules, and verifies system is ADB-ready.",
	RunE: func(cmd *cobra.Command, args []string) error {
		logger := zerolog.New(zerolog.ConsoleWriter{
			Out:     os.Stderr,
			NoColor: false,
		}).With().Timestamp().Logger()

		osu := runtime.NewOSUtils(logger, setupDryRun)

		fmt.Fprintln(cmd.OutOrStdout(), "Fire TV Sideloading Toolkit - System Setup")
		fmt.Fprintln(cmd.OutOrStdout(), "==========================================")

		// Run full verification first
		verify, err := osu.RunVerification()
		if err != nil {
			return errors.NewError(errors.ADBServerError,
				"Failed to run system verification", err)
		}

		// Track issues for summary
		issues := 0

		// 4. Package check phase
		fmt.Fprintln(cmd.OutOrStdout(), "\nChecking required packages...")
		for _, pkg := range verify.PackagesInstalled {
			fmt.Fprintf(cmd.OutOrStdout(), "  [OK] %s\n", pkg)
		}
		for _, pkg := range verify.PackagesMissing {
			if setupDryRun {
				fmt.Fprintf(cmd.OutOrStdout(), "  [dry-run] Would install: %s\n", pkg)
			} else {
				fmt.Fprintf(cmd.OutOrStdout(), "  Installing: %s...\n", pkg)
			}
		}
		if len(verify.PackagesMissing) > 0 && !setupDryRun {
			if err := osu.InstallPackages(verify.PackagesMissing); err != nil {
				if ce, ok := err.(*errors.ClassifiedError); ok {
					fmt.Fprintf(cmd.OutOrStdout(), "  Error: %s\n", ce.Message)
					fmt.Fprintf(cmd.OutOrStdout(), "  Recovery: %s\n", errors.Recovery(ce.Type))
				}
				return err
			}
			fmt.Fprintln(cmd.OutOrStdout(), "  All missing packages installed.")
		}

		// 5. udev rules phase
		fmt.Fprintln(cmd.OutOrStdout(), "\nConfiguring udev rules...")
		if verify.UdevRulesOk {
			fmt.Fprintln(cmd.OutOrStdout(), "  [OK] udev rules present")
		} else {
			if setupDryRun {
				fmt.Fprintln(cmd.OutOrStdout(), "  [dry-run] Would write 51-android.rules with Amazon + Android vendor IDs")
				issues++
			} else {
				if err := osu.InstallUdevRules(); err != nil {
					if ce, ok := err.(*errors.ClassifiedError); ok {
						fmt.Fprintf(cmd.OutOrStdout(), "  Error: %s\n", ce.Message)
						fmt.Fprintf(cmd.OutOrStdout(), "  Recovery: %s\n", errors.Recovery(ce.Type))
					}
					return err
				}
				fmt.Fprintln(cmd.OutOrStdout(), "  Installed 51-android.rules with Amazon + Android vendor IDs")
			}
		}

		// 6. Group membership phase
		fmt.Fprintln(cmd.OutOrStdout(), "\nChecking group membership...")
		if verify.InAdbusersGroup {
			fmt.Fprintln(cmd.OutOrStdout(), "  [OK] User in adbusers group")
		} else {
			fmt.Fprintln(cmd.OutOrStdout(), "  [MISSING] User not in adbusers group. Run: sudo usermod -aG adbusers $USER")
			issues++
		}

		// 7. Firewall phase
		fmt.Fprintln(cmd.OutOrStdout(), "\nChecking firewall...")
		if verify.FirewallOk {
			fmt.Fprintln(cmd.OutOrStdout(), "  [OK] No firewall blocking ADB")
		} else {
			fmt.Fprintln(cmd.OutOrStdout(), "  [WARN] Firewall may block ADB on port 5555. Ensure 5555/tcp is allowed.")
			issues++
		}

		// 8. Summary
		fmt.Fprintln(cmd.OutOrStdout(), "\n==========================================")
		if len(verify.PackagesMissing) > 0 && !setupDryRun {
			fmt.Fprintf(cmd.OutOrStdout(), "Setup complete: %d packages installed, %d issues found\n",
				len(verify.PackagesMissing), issues)
		} else if setupDryRun {
			fmt.Fprintf(cmd.OutOrStdout(), "Dry run: %d packages would be installed, %d issues found\n",
				len(verify.PackagesMissing), issues)
		} else {
			fmt.Fprintf(cmd.OutOrStdout(), "Setup complete: all packages present, %d issues found\n", issues)
		}

		if !verify.InAdbusersGroup {
			fmt.Fprintln(cmd.OutOrStdout(), "\nNOTE: Log out and back in for group changes to take effect")
		}

		// Determine exit behavior: return nil (exit 0) but print issues
		// The actual exit code is determined by the error return
		if issues > 0 && !setupDryRun {
			return errors.NewError(errors.PermissionError,
				fmt.Sprintf("%d setup issues require attention", issues), nil)
		}

		return nil
	},
}

func init() {
	setupCmd.Flags().BoolVar(&setupDryRun, "dry-run", false, "Show what would be done without installing")
	setupCmd.Flags().BoolVar(&setupSystemd, "systemd", false, "Generate systemd user service for ADB server (Phase 4)")
}
