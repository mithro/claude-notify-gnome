#!/usr/bin/env python3
"""
Terminal Finder Utility
Standalone utility for finding and focusing terminal windows containing Claude processes

This can be used for testing and debugging the terminal discovery system.
"""

import os
import sys
import subprocess
import logging
from typing import List, Optional, Dict, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TerminalDiscovery:
    """Advanced terminal discovery with multiple methods"""

    @staticmethod
    def get_all_processes() -> List[Dict]:
        """Get detailed process information"""
        processes = []
        try:
            # Use ps to get detailed process info
            result = subprocess.run([
                'ps', 'axo', 'pid,ppid,comm,args,cwd'
            ], capture_output=True, text=True)

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    parts = line.strip().split(None, 4)
                    if len(parts) >= 4:
                        try:
                            processes.append({
                                'pid': int(parts[0]),
                                'ppid': int(parts[1]),
                                'comm': parts[2],
                                'args': parts[3] if len(parts) > 3 else '',
                                'cwd': parts[4] if len(parts) > 4 else ''
                            })
                        except ValueError:
                            continue

        except Exception as e:
            logger.error(f"Failed to get process list: {e}")

        return processes

    @staticmethod
    def find_claude_processes() -> List[Dict]:
        """Find all Claude-related processes"""
        claude_processes = []
        processes = TerminalDiscovery.get_all_processes()

        for proc in processes:
            # Look for claude in command or args
            if ('claude' in proc['comm'].lower() or
                'claude' in proc['args'].lower()):
                claude_processes.append(proc)

        return claude_processes

    @staticmethod
    def find_processes_in_directory(target_dir: str) -> List[Dict]:
        """Find processes running in a specific directory"""
        matching_processes = []

        try:
            # Get absolute path
            target_dir = os.path.abspath(target_dir)

            # Look through /proc for processes with matching CWD
            for pid_dir in os.listdir('/proc'):
                if not pid_dir.isdigit():
                    continue

                try:
                    pid = int(pid_dir)
                    cwd_link = f"/proc/{pid}/cwd"

                    if os.path.exists(cwd_link):
                        actual_cwd = os.readlink(cwd_link)
                        if actual_cwd == target_dir:
                            # Get process info
                            with open(f"/proc/{pid}/comm", 'r') as f:
                                comm = f.read().strip()

                            with open(f"/proc/{pid}/cmdline", 'r') as f:
                                cmdline = f.read().replace('\0', ' ').strip()

                            with open(f"/proc/{pid}/stat", 'r') as f:
                                stat_data = f.read().split()
                                ppid = int(stat_data[3]) if len(stat_data) > 3 else 0

                            matching_processes.append({
                                'pid': pid,
                                'ppid': ppid,
                                'comm': comm,
                                'cmdline': cmdline,
                                'cwd': actual_cwd
                            })

                except (OSError, ValueError, IndexError):
                    continue

        except Exception as e:
            logger.error(f"Error finding processes in directory: {e}")

        return matching_processes

    @staticmethod
    def build_process_tree(processes: List[Dict]) -> Dict[int, List[int]]:
        """Build a process tree mapping parent PID to child PIDs"""
        tree = {}
        for proc in processes:
            ppid = proc['ppid']
            pid = proc['pid']

            if ppid not in tree:
                tree[ppid] = []
            tree[ppid].append(pid)

        return tree

    @staticmethod
    def walk_process_tree_up(start_pid: int, max_depth: int = 10) -> List[Tuple[int, str]]:
        """Walk up the process tree from a given PID"""
        path = []
        current_pid = start_pid

        for depth in range(max_depth):
            try:
                # Get process info
                with open(f"/proc/{current_pid}/comm", 'r') as f:
                    comm = f.read().strip()

                with open(f"/proc/{current_pid}/stat", 'r') as f:
                    stat_data = f.read().split()
                    ppid = int(stat_data[3]) if len(stat_data) > 3 else 0

                path.append((current_pid, comm))

                if ppid <= 1:  # Reached init
                    break

                current_pid = ppid

            except (OSError, ValueError, IndexError):
                break

        return path

    @staticmethod
    def find_terminal_windows() -> List[Dict]:
        """Find all terminal windows using wmctrl"""
        windows = []

        try:
            result = subprocess.run(['wmctrl', '-lp'], capture_output=True, text=True)

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 4:
                        window_id = parts[0]
                        desktop = parts[1]
                        window_pid = parts[2]
                        window_title = ' '.join(parts[4:]) if len(parts) > 4 else ''

                        try:
                            # Get process info for this window
                            pid = int(window_pid)
                            with open(f"/proc/{pid}/comm", 'r') as f:
                                comm = f.read().strip()

                            windows.append({
                                'window_id': window_id,
                                'desktop': desktop,
                                'pid': pid,
                                'comm': comm,
                                'title': window_title
                            })

                        except (ValueError, OSError):
                            continue

        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("wmctrl not available")

        return windows

    @staticmethod
    def find_gnome_terminal_tabs() -> List[Dict]:
        """Find GNOME Terminal tabs using D-Bus SearchProvider2"""
        tabs = []

        try:
            # Use dbus-send to query GNOME Terminal tabs
            result = subprocess.run([
                'dbus-send', '--session', '--dest=org.gnome.Terminal',
                '--print-reply=literal',
                '/org/gnome/Terminal/SearchProvider',
                'org.gnome.Shell.SearchProvider2.GetInitialResultSet',
                'array:string:""'
            ], capture_output=True, text=True)

            if result.returncode == 0:
                # Parse the output to get tab UUIDs
                output = result.stdout.strip()
                logger.debug(f"GNOME Terminal D-Bus response: {output}")

                # Extract tab IDs (this is a simplified parser)
                if 'array [' in output:
                    start = output.find('array [') + 7
                    end = output.find(']', start)
                    if end > start:
                        tab_data = output[start:end]
                        # Parse tab IDs (simplified)
                        for part in tab_data.split():
                            if part.startswith('"') and part.endswith('"'):
                                tab_id = part.strip('"')
                                tabs.append({'tab_id': tab_id})

        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.debug("GNOME Terminal D-Bus interface not available")

        return tabs

    @staticmethod
    def focus_gnome_terminal_wayland(target_cwd: str = None) -> bool:
        """Focus GNOME Terminal using Claude session correlation"""
        try:
            # Use the Claude terminal focuser
            import sys
            import os
            sys.path.insert(0, os.path.expanduser('~/.claude'))
            from claude_terminal_focuser import focus_terminal_window

            logger.info(f"Focusing terminal using Claude session correlation (target_cwd: {target_cwd})")
            success = focus_terminal_window(target_cwd)

            if success:
                logger.info("Successfully focused terminal using Claude session correlation")
                return True
            else:
                logger.warning("Failed to focus terminal using Claude session correlation")

        except Exception as e:
            logger.warning(f"Claude session correlation failed: {e}")

        # Fallback to basic Window Calls method
        try:
            result = subprocess.run([
                'gdbus', 'call', '--session',
                '--dest=org.gnome.Shell',
                '--object-path=/org/gnome/Shell/Extensions/Windows',
                '--method=org.gnome.Shell.Extensions.Windows.List'
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                import json
                windows_data = result.stdout.strip()
                if windows_data.startswith("('[") and windows_data.endswith("',)"):
                    json_str = windows_data[2:-3]
                    windows = json.loads(json_str)

                    terminal_windows = [w for w in windows if w.get('wm_class') == 'gnome-terminal-server']

                    if terminal_windows:
                        window_id = terminal_windows[0]['id']
                        activate_result = subprocess.run([
                            'gdbus', 'call', '--session',
                            '--dest=org.gnome.Shell',
                            '--object-path=/org/gnome/Shell/Extensions/Windows',
                            '--method=org.gnome.Shell.Extensions.Windows.Activate',
                            str(window_id)
                        ], capture_output=True, text=True, timeout=5)

                        if activate_result.returncode == 0:
                            logger.info(f"Successfully focused terminal using fallback method (ID: {window_id})")
                            return True
        except Exception as e:
            logger.debug(f"Fallback method failed: {e}")

        logger.warning("All terminal focus methods failed")
        return False

    @staticmethod
    def detect_session_type() -> str:
        """Detect if running on X11 or Wayland"""
        session_type = os.environ.get('XDG_SESSION_TYPE', 'unknown')
        return session_type

def analyze_current_session():
    """Analyze the current terminal session"""
    print("=== Current Terminal Session Analysis ===")

    # Get current process info
    current_pid = os.getpid()
    current_ppid = os.getppid()
    current_cwd = os.getcwd()

    print(f"Current PID: {current_pid}")
    print(f"Parent PID: {current_ppid}")
    print(f"Current CWD: {current_cwd}")

    # Walk up process tree
    print("\n=== Process Tree ===")
    tree_path = TerminalDiscovery.walk_process_tree_up(current_pid)
    for i, (pid, comm) in enumerate(tree_path):
        indent = "  " * i
        print(f"{indent}{pid}: {comm}")

    # Find processes in current directory
    print(f"\n=== Processes in {current_cwd} ===")
    dir_processes = TerminalDiscovery.find_processes_in_directory(current_cwd)
    for proc in dir_processes:
        print(f"PID {proc['pid']}: {proc['comm']} - {proc['cmdline'][:60]}...")

    # Find Claude processes
    print("\n=== Claude Processes ===")
    claude_procs = TerminalDiscovery.find_claude_processes()
    for proc in claude_procs:
        print(f"PID {proc['pid']}: {proc['comm']} - {proc['args'][:60]}...")

    # Find terminal windows
    print("\n=== Terminal Windows ===")
    windows = TerminalDiscovery.find_terminal_windows()
    terminal_windows = [w for w in windows if 'terminal' in w['comm'].lower()]
    for window in terminal_windows:
        print(f"Window {window['window_id']}: {window['comm']} - {window['title']}")

    # Find GNOME Terminal tabs
    print("\n=== GNOME Terminal Tabs ===")
    tabs = TerminalDiscovery.find_gnome_terminal_tabs()
    if tabs:
        for tab in tabs:
            print(f"Tab: {tab['tab_id']}")
    else:
        print("No tabs found or D-Bus interface not available")

def test_focus_current_terminal():
    """Test focusing the current terminal window"""
    print("\n=== Testing Terminal Focus ===")

    session_type = TerminalDiscovery.detect_session_type()
    print(f"Session type: {session_type}")

    # Walk up to find terminal
    tree_path = TerminalDiscovery.walk_process_tree_up(os.getpid())
    terminal_pid = None

    for pid, comm in tree_path:
        if 'terminal' in comm.lower():
            terminal_pid = pid
            print(f"Found terminal process: {pid} ({comm})")
            break

    if not terminal_pid:
        print("Could not find terminal process in tree")
        return

    if session_type == 'wayland':
        print("Using Wayland focus method...")
        if TerminalDiscovery.focus_gnome_terminal_wayland():
            print("Successfully focused terminal using Wayland method")
        else:
            print("Failed to focus terminal using Wayland method")
        return

    # X11 method (original logic)
    print("Using X11 focus method...")

    # Find window by PID
    windows = TerminalDiscovery.find_terminal_windows()
    target_window = None

    for window in windows:
        if window['pid'] == terminal_pid:
            target_window = window
            break

    if not target_window:
        print(f"Could not find window for terminal PID {terminal_pid}")
        return

    print(f"Found target window: {target_window['window_id']}")

    # Test focusing with wmctrl
    try:
        result = subprocess.run([
            'wmctrl', '-ia', target_window['window_id']
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("Successfully focused window with wmctrl")
        else:
            print(f"Failed to focus with wmctrl: {result.stderr}")

    except FileNotFoundError:
        print("wmctrl not available")

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "analyze":
            analyze_current_session()
        elif command == "focus":
            test_focus_current_terminal()
        elif command == "directory" and len(sys.argv) > 2:
            directory = sys.argv[2]
            print(f"=== Processes in {directory} ===")
            processes = TerminalDiscovery.find_processes_in_directory(directory)
            for proc in processes:
                print(f"PID {proc['pid']}: {proc['comm']} - {proc['cmdline'][:60]}...")
        else:
            print("Unknown command")
            print("Usage: terminal-finder.py [analyze|focus|directory <path>]")
    else:
        print("Terminal Finder Utility")
        print("Usage: terminal-finder.py [analyze|focus|directory <path>]")
        print("")
        print("Commands:")
        print("  analyze   - Analyze current terminal session")
        print("  focus     - Test focusing current terminal")
        print("  directory - Find processes in specified directory")

if __name__ == "__main__":
    main()