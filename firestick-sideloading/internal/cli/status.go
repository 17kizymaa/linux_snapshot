package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show current device connection health",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Fprintln(cmd.OutOrStdout(), "Status not yet implemented.")
		fmt.Fprintln(cmd.OutOrStdout(), "Expected: show current device info and health check result.")
		return nil
	},
}
