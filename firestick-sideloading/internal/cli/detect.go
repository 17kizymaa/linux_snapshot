package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

var detectCmd = &cobra.Command{
	Use:   "detect",
	Short: "Quick scan for connected Fire TV devices",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Fprintln(cmd.OutOrStdout(), "Detect not yet implemented.")
		fmt.Fprintln(cmd.OutOrStdout(), "Expected: scan and display connected device info (model, Fire OS, SDK).")
		return nil
	},
}
