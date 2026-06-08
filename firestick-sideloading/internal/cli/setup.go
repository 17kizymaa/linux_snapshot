package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

var (
	setupDryRun  bool
	setupSystemd bool
)

var setupCmd = &cobra.Command{
	Use:   "setup",
	Short: "Arch Linux one-time setup helper",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Fprintln(cmd.OutOrStdout(), "Setup not yet implemented.")
		fmt.Fprintf(cmd.OutOrStdout(), "Expected: Arch bootstrap (dry-run=%v, systemd=%v)\n", setupDryRun, setupSystemd)
		return nil
	},
}

func init() {
	setupCmd.Flags().BoolVar(&setupDryRun, "dry-run", false, "Show what would be done without installing")
	setupCmd.Flags().BoolVar(&setupSystemd, "systemd", false, "Generate systemd user service for ADB server (Phase 4)")
}
