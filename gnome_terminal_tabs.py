#!/usr/bin/env python3
"""
GNOME Terminal Tab Control Library

This library provides programmatic control over GNOME Terminal tabs using the
org.gnome.Shell.SearchProvider2 D-Bus interface. This interface is normally
used by GNOME Shell's search functionality but can be repurposed to list,
query, and focus terminal tabs.

Example:
    >>> import gnome_terminal_tabs as gtt
    >>>
    >>> # List all open tabs
    >>> tabs = gtt.list_tabs()
    >>> for tab in tabs:
    >>>     print(f"{tab.uuid}: {tab.title}")
    >>>
    >>> # Focus a specific tab by UUID
    >>> gtt.focus_tab("abc-def-123-456")
    >>>
    >>> # Find and focus a tab by working directory
    >>> tab = gtt.find_tab_by_directory("/home/user/project")
    >>> if tab:
    >>>     gtt.focus_tab(tab.uuid)

Requirements:
    - GNOME Terminal running on D-Bus session bus
    - python3-dbus package installed

API Reference:
    Classes:
        - TerminalTab: Represents a terminal tab with UUID, title, and metadata

    Functions:
        - list_tabs() -> List[TerminalTab]: Get all open terminal tabs
        - focus_tab(uuid: str) -> bool: Focus a specific tab by UUID
        - find_tab_by_directory(directory: str) -> Optional[TerminalTab]: Find tab by working directory
        - find_tab_by_title(title: str) -> Optional[TerminalTab]: Find tab by title pattern
        - get_current_tab_uuid() -> Optional[str]: Get UUID of current terminal tab
"""

import dbus
import os
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class TerminalTab:
    """
    Represents a GNOME Terminal tab.

    Attributes:
        uuid (str): Unique identifier for the tab (used with D-Bus operations)
        title (str): The tab's title (typically shows working directory)
        description (str): Additional tab information
        metadata (dict): Raw metadata from D-Bus
    """
    uuid: str
    title: str
    description: str
    metadata: Dict[str, Any]

    def __repr__(self):
        return f"TerminalTab(uuid='{self.uuid[:8]}...', title='{self.title}')"


class GnomeTerminalError(Exception):
    """Base exception for GNOME Terminal operations"""
    pass


class TabNotFoundError(GnomeTerminalError):
    """Raised when a terminal tab cannot be found"""
    pass


class DBusConnectionError(GnomeTerminalError):
    """Raised when D-Bus connection fails"""
    pass


def _get_search_provider_interface():
    """
    Get the GNOME Terminal SearchProvider D-Bus interface.

    Returns:
        dbus.Interface: The SearchProvider2 interface

    Raises:
        DBusConnectionError: If connection to D-Bus or GNOME Terminal fails
    """
    try:
        bus = dbus.SessionBus()
        terminal = bus.get_object(
            'org.gnome.Terminal',
            '/org/gnome/Terminal/SearchProvider'
        )
        return dbus.Interface(terminal, 'org.gnome.Shell.SearchProvider2')
    except dbus.exceptions.DBusException as e:
        raise DBusConnectionError(f"Failed to connect to GNOME Terminal D-Bus: {e}")


def list_tabs() -> List[TerminalTab]:
    """
    Get a list of all open GNOME Terminal tabs.

    Returns:
        List[TerminalTab]: List of all terminal tabs with their metadata

    Raises:
        DBusConnectionError: If D-Bus connection fails

    Example:
        >>> tabs = list_tabs()
        >>> for tab in tabs:
        >>>     print(f"Tab: {tab.title}")
    """
    search_provider = _get_search_provider_interface()

    try:
        # GetInitialResultSet returns list of tab UUIDs
        tab_ids = search_provider.GetInitialResultSet([])

        if not tab_ids:
            return []

        # GetResultMetas returns metadata for each tab
        metas = search_provider.GetResultMetas(tab_ids)

        tabs = []
        for tab_id, meta in zip(tab_ids, metas):
            tab = TerminalTab(
                uuid=str(tab_id),
                title=str(meta.get('name', '')),
                description=str(meta.get('description', '')),
                metadata=dict(meta)
            )
            tabs.append(tab)

        return tabs
    except dbus.exceptions.DBusException as e:
        raise GnomeTerminalError(f"Failed to list tabs: {e}")


def focus_tab(uuid: str) -> bool:
    """
    Focus a specific terminal tab and bring its window to the foreground.

    This uses the SearchProvider's ActivateResult method, which is designed
    to open search results. When given a tab UUID, it switches to that tab
    and focuses the terminal window.

    Args:
        uuid (str): The UUID of the tab to focus

    Returns:
        bool: True if successful, False otherwise

    Example:
        >>> if focus_tab("abc-def-123-456"):
        >>>     print("Tab focused successfully")
    """
    search_provider = _get_search_provider_interface()

    try:
        # ActivateResult(id, terms, timestamp)
        # - id: The tab UUID to activate
        # - terms: Search terms (unused, pass empty array)
        # - timestamp: Event timestamp (unused, pass 0)
        search_provider.ActivateResult(uuid, [], 0)
        return True
    except dbus.exceptions.DBusException as e:
        # Don't raise exception, just return False for failures
        return False


def find_tab_by_directory(directory: str) -> Optional[TerminalTab]:
    """
    Find a terminal tab by its working directory.

    This searches tab titles for the directory name, as GNOME Terminal
    typically includes the working directory in the tab title.

    Args:
        directory (str): The working directory to search for (full path or basename)

    Returns:
        Optional[TerminalTab]: The matching tab, or None if not found

    Example:
        >>> tab = find_tab_by_directory("/home/user/project")
        >>> if tab:
        >>>     focus_tab(tab.uuid)
    """
    tabs = list_tabs()

    # Try to match full path first
    for tab in tabs:
        if directory in tab.title:
            return tab

    # Try basename if full path didn't match
    basename = os.path.basename(directory)
    if basename:
        for tab in tabs:
            if basename in tab.title:
                return tab

    return None


def find_tab_by_title(pattern: str, case_sensitive: bool = False) -> Optional[TerminalTab]:
    """
    Find a terminal tab by matching a pattern in its title.

    Args:
        pattern (str): The pattern to search for in tab titles
        case_sensitive (bool): Whether the search should be case-sensitive

    Returns:
        Optional[TerminalTab]: The first matching tab, or None if not found

    Example:
        >>> tab = find_tab_by_title("claude")
        >>> if tab:
        >>>     print(f"Found Claude tab: {tab.title}")
    """
    tabs = list_tabs()

    if case_sensitive:
        for tab in tabs:
            if pattern in tab.title:
                return tab
    else:
        pattern_lower = pattern.lower()
        for tab in tabs:
            if pattern_lower in tab.title.lower():
                return tab

    return None


def find_tabs_by_title(pattern: str, case_sensitive: bool = False) -> List[TerminalTab]:
    """
    Find all terminal tabs matching a pattern in their title.

    Args:
        pattern (str): The pattern to search for in tab titles
        case_sensitive (bool): Whether the search should be case-sensitive

    Returns:
        List[TerminalTab]: All matching tabs (empty list if none found)

    Example:
        >>> tabs = find_tabs_by_title("bash")
        >>> print(f"Found {len(tabs)} bash tabs")
    """
    tabs = list_tabs()
    matching = []

    if case_sensitive:
        for tab in tabs:
            if pattern in tab.title:
                matching.append(tab)
    else:
        pattern_lower = pattern.lower()
        for tab in tabs:
            if pattern_lower in tab.title.lower():
                matching.append(tab)

    return matching


def get_current_tab_uuid() -> Optional[str]:
    """
    Get the UUID of the current terminal tab.

    This reads the GNOME_TERMINAL_SCREEN environment variable and converts
    it to the D-Bus UUID format.

    Returns:
        Optional[str]: The current tab's UUID, or None if not in a GNOME Terminal

    Example:
        >>> uuid = get_current_tab_uuid()
        >>> if uuid:
        >>>     print(f"Current tab UUID: {uuid}")
    """
    screen_path = os.environ.get('GNOME_TERMINAL_SCREEN', '')
    if not screen_path:
        return None

    return extract_uuid_from_screen_path(screen_path)


def extract_uuid_from_screen_path(screen_path: str) -> Optional[str]:
    """
    Extract UUID from GNOME_TERMINAL_SCREEN environment variable.

    The environment variable has format: /org/gnome/Terminal/screen/UUID_WITH_UNDERSCORES
    The D-Bus API expects format: UUID-WITH-HYPHENS

    Args:
        screen_path (str): The GNOME_TERMINAL_SCREEN path

    Returns:
        Optional[str]: The UUID in D-Bus format, or None if parsing fails

    Example:
        >>> uuid = extract_uuid_from_screen_path("/org/gnome/Terminal/screen/abc_def_123")
        >>> print(uuid)  # "abc-def-123"
    """
    match = re.search(r'/org/gnome/Terminal/screen/([a-f0-9_]+)', screen_path)
    if match:
        # Convert underscores to hyphens for D-Bus format
        return match.group(1).replace('_', '-')
    return None


def focus_tab_by_directory(directory: str) -> bool:
    """
    Convenience function to find and focus a tab by working directory.

    Args:
        directory (str): The working directory to search for

    Returns:
        bool: True if a tab was found and focused, False otherwise

    Example:
        >>> if focus_tab_by_directory("/home/user/project"):
        >>>     print("Focused project tab")
    """
    tab = find_tab_by_directory(directory)
    if tab:
        return focus_tab(tab.uuid)
    return False


def focus_tab_by_title(pattern: str) -> bool:
    """
    Convenience function to find and focus a tab by title pattern.

    Args:
        pattern (str): The pattern to search for in tab titles

    Returns:
        bool: True if a tab was found and focused, False otherwise

    Example:
        >>> if focus_tab_by_title("claude"):
        >>>     print("Focused Claude tab")
    """
    tab = find_tab_by_title(pattern)
    if tab:
        return focus_tab(tab.uuid)
    return False


# Convenience aliases for common operations
get_tabs = list_tabs
switch_to_tab = focus_tab
