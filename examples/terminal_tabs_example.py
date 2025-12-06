#!/usr/bin/env python3
"""
Example usage script for gnome_terminal_tabs library

This script demonstrates various ways to interact with GNOME Terminal tabs
using the gnome_terminal_tabs library.
"""

import sys
import os

# Add parent directory to path to import the library
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gnome_terminal_tabs as gtt


def example_list_all_tabs():
    """Example: List all open terminal tabs"""
    print("=" * 80)
    print("Example 1: List all terminal tabs")
    print("=" * 80)

    try:
        tabs = gtt.list_tabs()
        print(f"Found {len(tabs)} open terminal tabs:\n")

        for i, tab in enumerate(tabs):
            print(f"Tab {i}:")
            print(f"  UUID: {tab.uuid}")
            print(f"  Title: {tab.title}")
            if tab.description:
                desc = tab.description.strip()
                if desc:
                    print(f"  Description: {desc[:80]}...")
            print()

        return tabs
    except gtt.GnomeTerminalError as e:
        print(f"Error: {e}")
        return []


def example_get_current_tab():
    """Example: Get information about the current tab"""
    print("=" * 80)
    print("Example 2: Get current tab UUID")
    print("=" * 80)

    uuid = gtt.get_current_tab_uuid()
    if uuid:
        print(f"Current tab UUID: {uuid}\n")

        # Find the tab in the list
        tabs = gtt.list_tabs()
        for tab in tabs:
            if tab.uuid == uuid:
                print(f"Current tab title: {tab.title}")
                break
    else:
        print("Not running in a GNOME Terminal or GNOME_TERMINAL_SCREEN not set\n")

    return uuid


def example_focus_by_uuid(uuid):
    """Example: Focus a tab by its UUID"""
    print("=" * 80)
    print("Example 3: Focus a tab by UUID")
    print("=" * 80)

    print(f"Attempting to focus tab: {uuid}")
    if gtt.focus_tab(uuid):
        print("✓ Successfully focused the tab!\n")
        return True
    else:
        print("✗ Failed to focus the tab\n")
        return False


def example_find_by_directory():
    """Example: Find and focus a tab by working directory"""
    print("=" * 80)
    print("Example 4: Find tab by working directory")
    print("=" * 80)

    cwd = os.getcwd()
    print(f"Looking for tab with directory: {cwd}")

    tab = gtt.find_tab_by_directory(cwd)
    if tab:
        print(f"✓ Found tab: {tab.title}")
        print(f"  UUID: {tab.uuid}")

        print("\nFocusing this tab...")
        if gtt.focus_tab(tab.uuid):
            print("✓ Successfully focused!\n")
        else:
            print("✗ Failed to focus\n")
    else:
        print(f"✗ No tab found with directory '{cwd}'\n")


def example_find_by_title():
    """Example: Find tabs by title pattern"""
    print("=" * 80)
    print("Example 5: Find tabs by title pattern")
    print("=" * 80)

    pattern = "bash"  # Common pattern in terminal titles
    print(f"Searching for tabs with '{pattern}' in title...")

    tabs = gtt.find_tabs_by_title(pattern)
    if tabs:
        print(f"✓ Found {len(tabs)} matching tab(s):\n")
        for tab in tabs:
            print(f"  - {tab.title} (UUID: {tab.uuid[:16]}...)")
        print()
    else:
        print(f"✗ No tabs found matching '{pattern}'\n")


def example_convenience_functions():
    """Example: Using convenience functions"""
    print("=" * 80)
    print("Example 6: Convenience functions")
    print("=" * 80)

    print("Using get_tabs() alias:")
    tabs = gtt.get_tabs()
    print(f"  Found {len(tabs)} tabs")

    if tabs:
        print("\nUsing switch_to_tab() alias:")
        uuid = tabs[0].uuid
        print(f"  Switching to first tab: {tabs[0].title}")
        if gtt.switch_to_tab(uuid):
            print("  ✓ Success!")
        else:
            print("  ✗ Failed")

    print()


def interactive_mode():
    """Interactive mode: Let user choose a tab to focus"""
    print("=" * 80)
    print("Interactive Mode: Choose a tab to focus")
    print("=" * 80)

    tabs = gtt.list_tabs()
    if not tabs:
        print("No terminal tabs found.")
        return

    print("\nAvailable tabs:")
    for i, tab in enumerate(tabs):
        print(f"  {i}: {tab.title}")

    try:
        choice = input("\nEnter tab number to focus (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            return

        index = int(choice)
        if 0 <= index < len(tabs):
            tab = tabs[index]
            print(f"\nFocusing tab: {tab.title}")
            if gtt.focus_tab(tab.uuid):
                print("✓ Successfully focused!")
            else:
                print("✗ Failed to focus")
        else:
            print(f"Invalid index: {index}")
    except ValueError:
        print("Invalid input")
    except KeyboardInterrupt:
        print("\nCancelled")


def main():
    """Run all examples or interactive mode"""
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_mode()
        return

    print("GNOME Terminal Tabs Library - Example Usage\n")

    # Example 1: List all tabs
    tabs = example_list_all_tabs()

    if not tabs:
        print("No terminal tabs found. Make sure GNOME Terminal is running.")
        return

    # Example 2: Get current tab
    current_uuid = example_get_current_tab()

    # Example 3: Focus current tab (if we found it)
    if current_uuid:
        example_focus_by_uuid(current_uuid)

    # Example 4: Find by directory
    example_find_by_directory()

    # Example 5: Find by title
    example_find_by_title()

    # Example 6: Convenience functions
    example_convenience_functions()

    # Offer interactive mode
    print("\nRun with --interactive flag for interactive tab selection")


if __name__ == '__main__':
    try:
        main()
    except gtt.DBusConnectionError as e:
        print(f"Error: {e}")
        print("\nMake sure GNOME Terminal is running and D-Bus is available.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
