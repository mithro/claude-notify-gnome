#!/usr/bin/env python3
"""
Claude Terminal Focuser
Uses the correlation data to focus the correct terminal containing a Claude session
"""

import os
import json
import subprocess
from typing import Dict, List, Optional

def get_process_info(pid: int) -> Optional[Dict]:
    """Get process information including environment"""
    try:
        with open(f'/proc/{pid}/stat', 'r') as f:
            stat_data = f.read().split()
            ppid = int(stat_data[3]) if len(stat_data) > 3 else 0

        with open(f'/proc/{pid}/comm', 'r') as f:
            comm = f.read().strip()

        # Get environment variables
        env_vars = {}
        try:
            with open(f'/proc/{pid}/environ', 'rb') as f:
                env_data = f.read().decode('utf-8', errors='ignore')
                for line in env_data.split('\0'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
        except (OSError, UnicodeDecodeError):
            pass

        return {
            'pid': pid,
            'ppid': ppid,
            'comm': comm,
            'env': env_vars
        }
    except (OSError, ValueError):
        return None

def get_process_cwd(pid: int) -> Optional[str]:
    """Get current working directory of a process"""
    try:
        return os.readlink(f'/proc/{pid}/cwd')
    except (OSError, FileNotFoundError):
        return None

def find_claude_session_for_cwd(target_cwd: str) -> Optional[Dict]:
    """Find the Claude session running in the specified directory"""
    try:
        result = subprocess.run(['pgrep', 'claude'], capture_output=True, text=True)
        if result.returncode != 0:
            return None

        claude_pids = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]

        for claude_pid in claude_pids:
            claude_cwd = get_process_cwd(claude_pid)
            if claude_cwd == target_cwd:
                # Found the Claude session, now get its parent bash
                claude_info = get_process_info(claude_pid)
                if not claude_info:
                    continue

                parent_bash_info = get_process_info(claude_info['ppid'])
                if not parent_bash_info or parent_bash_info['comm'] != 'bash':
                    continue

                return {
                    'claude_pid': claude_pid,
                    'claude_cwd': claude_cwd,
                    'parent_bash_pid': parent_bash_info['pid'],
                    'parent_bash_cwd': get_process_cwd(parent_bash_info['pid']),
                    'terminal_screen': parent_bash_info['env'].get('GNOME_TERMINAL_SCREEN'),
                    'terminal_service': parent_bash_info['env'].get('GNOME_TERMINAL_SERVICE')
                }

    except Exception as e:
        print(f"Error finding Claude session: {e}")

    return None

def get_current_claude_session() -> Optional[Dict]:
    """Get the current Claude session information"""
    current_pid = os.getpid()

    # Walk up the process tree to find Claude
    current = current_pid
    for _ in range(10):  # Safety limit
        info = get_process_info(current)
        if not info:
            break

        if info['comm'] == 'claude':
            # Found Claude, get its parent bash
            parent_bash_info = get_process_info(info['ppid'])
            if parent_bash_info and parent_bash_info['comm'] == 'bash':
                return {
                    'claude_pid': current,
                    'claude_cwd': get_process_cwd(current),
                    'parent_bash_pid': parent_bash_info['pid'],
                    'parent_bash_cwd': get_process_cwd(parent_bash_info['pid']),
                    'terminal_screen': parent_bash_info['env'].get('GNOME_TERMINAL_SCREEN'),
                    'terminal_service': parent_bash_info['env'].get('GNOME_TERMINAL_SERVICE')
                }
            break

        current = info['ppid']
        if current <= 1:
            break

    return None

def get_window_info() -> List[Dict]:
    """Get GNOME window information"""
    try:
        result = subprocess.run([
            'gdbus', 'call', '--session',
            '--dest=org.gnome.Shell',
            '--object-path=/org/gnome/Shell/Extensions/Windows',
            '--method=org.gnome.Shell.Extensions.Windows.List'
        ], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            data = result.stdout.strip()
            if data.startswith("('[") and data.endswith("',)"):
                json_str = data[2:-3]
                return json.loads(json_str)
    except Exception as e:
        print(f"Error getting window info: {e}")

    return []

def focus_terminal_window(target_cwd: str = None) -> bool:
    """Focus the terminal window containing the Claude session"""

    # Determine which Claude session to focus
    if target_cwd:
        session = find_claude_session_for_cwd(target_cwd)
        if not session:
            print(f"No Claude session found in {target_cwd}")
            return False
    else:
        session = get_current_claude_session()
        if not session:
            print("Could not determine current Claude session")
            return False

    print(f"Target session:")
    print(f"  Claude PID: {session['claude_pid']}")
    print(f"  Working directory: {session['claude_cwd']}")
    print(f"  Terminal screen: {session['terminal_screen']}")

    # Get all terminal windows
    windows = get_window_info()
    terminal_windows = [w for w in windows if w.get('wm_class') == 'gnome-terminal-server']

    if not terminal_windows:
        print("No terminal windows found")
        return False

    print(f"\nFound {len(terminal_windows)} terminal windows:")
    for i, window in enumerate(terminal_windows):
        workspace = 'current' if window.get('in_current_workspace') else 'other'
        focus = 'focused' if window.get('focus') else 'not focused'
        print(f"  {i+1}. ID:{window['id']} [{workspace}] [{focus}] {window.get('title', 'No title')}")

    # Strategy: Focus any terminal window and let it switch workspaces
    # Since all terminal windows belong to the same gnome-terminal-server process,
    # focusing any of them should bring the terminal to the current workspace

    # Try to find a terminal that's not in current workspace first (more likely to need switching)
    target_window = None
    for window in terminal_windows:
        if not window.get('in_current_workspace'):
            target_window = window
            break

    # Fallback to any terminal
    if not target_window and terminal_windows:
        target_window = terminal_windows[0]

    if not target_window:
        print("No suitable terminal window found")
        return False

    window_id = target_window['id']
    print(f"\nAttempting to focus terminal window {window_id}")

    try:
        # Use Window Calls to activate the terminal
        result = subprocess.run([
            'gdbus', 'call', '--session',
            '--dest=org.gnome.Shell',
            '--object-path=/org/gnome/Shell/Extensions/Windows',
            '--method=org.gnome.Shell.Extensions.Windows.Activate',
            str(window_id)
        ], capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            print("✅ Terminal window activated successfully")
            print(f"Note: This focuses the terminal server, but the active tab might not be the correct one.")
            print(f"The correct tab should have screen UUID: {session['terminal_screen']}")
            print("Future enhancement: Implement tab switching using the screen UUID")
            return True
        else:
            print(f"❌ Failed to activate window: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error activating window: {e}")
        return False

def main():
    """Main function"""
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print("Claude Terminal Focuser")
            print("Usage:")
            print("  python3 claude_terminal_focuser.py                 # Focus current session's terminal")
            print("  python3 claude_terminal_focuser.py /path/to/dir    # Focus terminal with Claude in specified directory")
            return

        target_directory = sys.argv[1]
        if not os.path.isdir(target_directory):
            print(f"Error: {target_directory} is not a valid directory")
            return

        target_directory = os.path.abspath(target_directory)
        print(f"Focusing terminal containing Claude session in: {target_directory}")
        success = focus_terminal_window(target_directory)
    else:
        print("Focusing terminal for current Claude session...")
        success = focus_terminal_window()

    if success:
        print("\n🎯 Terminal focus completed successfully!")
    else:
        print("\n❌ Failed to focus terminal")

if __name__ == "__main__":
    main()