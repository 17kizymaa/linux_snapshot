package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

var devicesCmd = &cobra.Command{
	Use:   "devices",
	Short: "List all detected Fire TV devices",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Fprintln(cmd.OutOrStdout(), "Device detection not yet implemented.")
		fmt.Fprintln(cmd.OutOrStdout(), "Expected: list all ADB devices with model, state, connection type.")
		return nil
	},
}
