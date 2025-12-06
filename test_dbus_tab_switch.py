#!/usr/bin/env python3
"""
Test script for D-Bus tab switching in GNOME Terminal
"""
import dbus
import sys
import os
import re

def extract_uuid_from_screen_path(screen_path):
    """Extract UUID from GNOME_TERMINAL_SCREEN path"""
    # Format: /org/gnome/Terminal/screen/UUID_WITH_UNDERSCORES
    match = re.search(r'/org/gnome/Terminal/screen/([a-f0-9_]+)', screen_path)
    if match:
        # Convert underscores to hyphens for D-Bus format
        return match.group(1).replace('_', '-')
    return None

def get_all_terminal_tabs():
    """Get all terminal tabs via D-Bus SearchProvider"""
    try:
        bus = dbus.SessionBus()
        terminal = bus.get_object('org.gnome.Terminal', '/org/gnome/Terminal/SearchProvider')
        search_provider = dbus.Interface(terminal, 'org.gnome.Shell.SearchProvider2')

        # Get all tabs
        tab_ids = search_provider.GetInitialResultSet([])

        # Get metadata for all tabs
        if tab_ids:
            metas = search_provider.GetResultMetas(tab_ids)
            return list(zip(tab_ids, metas))
        return []
    except Exception as e:
        print(f"Error getting terminal tabs: {e}")
        return []

def focus_terminal_tab_by_uuid(uuid):
    """Focus a specific terminal tab by UUID"""
    try:
        bus = dbus.SessionBus()
        terminal = bus.get_object('org.gnome.Terminal', '/org/gnome/Terminal/SearchProvider')
        search_provider = dbus.Interface(terminal, 'org.gnome.Shell.SearchProvider2')

        # Activate the tab
        search_provider.ActivateResult(uuid, [], 0)
        return True
    except Exception as e:
        print(f"Error focusing tab {uuid}: {e}")
        return False

def find_tab_by_working_directory(cwd):
    """Find a tab by its working directory in the title"""
    tabs = get_all_terminal_tabs()

    for tab_id, meta in tabs:
        name = meta.get('name', '')
        description = meta.get('description', '')

        # Check if the directory appears in the tab name
        if cwd in name or os.path.basename(cwd) in name:
            return tab_id, meta

    return None, None

def main():
    # Get current terminal screen from environment
    current_screen = os.environ.get('GNOME_TERMINAL_SCREEN', '')
    current_uuid = extract_uuid_from_screen_path(current_screen)

    print(f"Current terminal screen: {current_screen}")
    print(f"Current UUID: {current_uuid}")
    print()

    # List all tabs
    print("All terminal tabs:")
    print("-" * 80)
    tabs = get_all_terminal_tabs()

    for i, (tab_id, meta) in enumerate(tabs):
        name = meta.get('name', 'Unnamed')
        is_current = " (CURRENT)" if tab_id == current_uuid else ""
        print(f"{i}: {tab_id}")
        print(f"   Name: {name}{is_current}")
        if meta.get('description'):
            desc = meta['description'].strip()
            if desc:
                print(f"   Description: {desc[:100]}...")
        print()

    # Test focusing
    if len(sys.argv) > 1:
        if sys.argv[1] == '--focus-current':
            if current_uuid:
                print(f"Attempting to focus current tab: {current_uuid}")
                if focus_terminal_tab_by_uuid(current_uuid):
                    print("Success!")
                else:
                    print("Failed!")
        elif sys.argv[1] == '--focus-index':
            if len(sys.argv) > 2:
                try:
                    index = int(sys.argv[2])
                    if 0 <= index < len(tabs):
                        tab_id = tabs[index][0]
                        print(f"Focusing tab {index}: {tab_id}")
                        if focus_terminal_tab_by_uuid(tab_id):
                            print("Success!")
                        else:
                            print("Failed!")
                    else:
                        print(f"Invalid index: {index}")
                except ValueError:
                    print("Invalid index")
        elif sys.argv[1] == '--focus-directory':
            if len(sys.argv) > 2:
                target_dir = sys.argv[2]
                tab_id, meta = find_tab_by_working_directory(target_dir)
                if tab_id:
                    print(f"Found tab for directory '{target_dir}': {tab_id}")
                    print(f"Tab name: {meta.get('name', 'Unnamed')}")
                    if focus_terminal_tab_by_uuid(tab_id):
                        print("Successfully focused tab!")
                    else:
                        print("Failed to focus tab!")
                else:
                    print(f"No tab found for directory '{target_dir}'")
    else:
        print("\nUsage:")
        print("  python3 test_dbus_tab_switch.py                    # List all tabs")
        print("  python3 test_dbus_tab_switch.py --focus-current    # Focus current tab")
        print("  python3 test_dbus_tab_switch.py --focus-index N    # Focus tab by index")
        print("  python3 test_dbus_tab_switch.py --focus-directory DIR  # Focus tab by directory")

if __name__ == '__main__':
    main()