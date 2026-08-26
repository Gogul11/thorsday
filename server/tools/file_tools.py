from pathlib import Path
from typing import Optional
from langchain.tools import tool


@tool
def list_directory(path: str = ".") -> str:
    """
    List files and directories inside the given directory.
    """
    try:
        directory = Path(path).expanduser().resolve()

        if not directory.exists():
            return f"Directory does not exist: {directory}"

        if not directory.is_dir():
            return f"Path is not a directory: {directory}"

        items = []

        for item in sorted(directory.iterdir()):
            item_type = "DIR" if item.is_dir() else "FILE"
            items.append(f"{item_type}: {item.name}")

        if not items:
            return f"Directory is empty: {directory}"

        return "\n".join(items)

    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def search_files(
    directory: str,
    pattern: str
) -> str:
    """
    Search recursively for files matching a pattern.
    Example patterns: *.txt, *.py, resume*
    """
    try:
        root = Path(directory).expanduser().resolve()

        if not root.exists():
            return f"Directory does not exist: {root}"

        if not root.is_dir():
            return f"Path is not a directory: {root}"

        matches = list(root.rglob(pattern))

        if not matches:
            return f"No files found matching '{pattern}' in {root}"

        results = []

        for match in matches:
            results.append(str(match))

        return "\n".join(results)

    except Exception as e:
        return f"Error searching files: {str(e)}"


@tool
def read_file(path: str) -> str:
    """
    Read the contents of a text file.
    """
    try:
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            return f"File does not exist: {file_path}"

        if not file_path.is_file():
            return f"Path is not a file: {file_path}"

        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Cannot read '{file_path}' as a UTF-8 text file."

    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def get_file_info(path: str) -> str:
    """
    Get metadata about a file or directory.
    """
    try:
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            return f"Path does not exist: {file_path}"

        stat = file_path.stat()

        file_type = "Directory" if file_path.is_dir() else "File"

        return (
            f"Path: {file_path}\n"
            f"Type: {file_type}\n"
            f"Size: {stat.st_size} bytes\n"
            f"Modified: {stat.st_mtime}"
        )

    except Exception as e:
        return f"Error getting file information: {str(e)}"


@tool
def create_file(path: str, content: str = "") -> str:
    """
    Create a new text file with the provided content.
    """
    try:
        file_path = Path(path).expanduser().resolve()

        if file_path.exists():
            return f"File already exists: {file_path}"

        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding="utf-8")

        return f"File created successfully: {file_path}"

    except Exception as e:
        return f"Error creating file: {str(e)}"


@tool
def write_file(path: str, content: str) -> str:
    """
    Write content to a text file, replacing existing content.
    """
    try:
        file_path = Path(path).expanduser().resolve()

        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding="utf-8")

        return f"File written successfully: {file_path}"

    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def append_to_file(path: str, content: str) -> str:
    """
    Append content to an existing text file.
    """
    try:
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            return f"File does not exist: {file_path}"

        if not file_path.is_file():
            return f"Path is not a file: {file_path}"

        with file_path.open("a", encoding="utf-8") as file:
            file.write(content)

        return f"Content appended successfully: {file_path}"

    except Exception as e:
        return f"Error appending to file: {str(e)}"


@tool
def create_directory(path: str) -> str:
    """
    Create a directory.
    """
    try:
        directory = Path(path).expanduser().resolve()

        if directory.exists():
            if directory.is_dir():
                return f"Directory already exists: {directory}"

            return f"A file already exists at this path: {directory}"

        directory.mkdir(parents=True, exist_ok=False)

        return f"Directory created successfully: {directory}"

    except Exception as e:
        return f"Error creating directory: {str(e)}"


@tool
def rename_path(
    old_path: str,
    new_name: str
) -> str:
    """
    Rename a file or directory.
    """
    try:
        source = Path(old_path).expanduser().resolve()

        if not source.exists():
            return f"Path does not exist: {source}"

        destination = source.parent / new_name

        if destination.exists():
            return f"Destination already exists: {destination}"

        source.rename(destination)

        return f"Renamed successfully:\n{source}\n→ {destination}"

    except Exception as e:
        return f"Error renaming path: {str(e)}"


@tool
def move_path(
    source_path: str,
    destination_directory: str
) -> str:
    """
    Move a file or directory into another directory.
    """
    try:
        source = Path(source_path).expanduser().resolve()
        destination = Path(destination_directory).expanduser().resolve()

        if not source.exists():
            return f"Source does not exist: {source}"

        if not destination.exists():
            return f"Destination directory does not exist: {destination}"

        if not destination.is_dir():
            return f"Destination is not a directory: {destination}"

        target = destination / source.name

        if target.exists():
            return f"Destination already contains: {target}"

        source.rename(target)

        return f"Moved successfully:\n{source}\n→ {target}"

    except Exception as e:
        return f"Error moving path: {str(e)}"


@tool
def delete_path(path: str) -> str:
    """
    Delete a file or an empty directory.
    """
    try:
        target = Path(path).expanduser().resolve()

        if not target.exists():
            return f"Path does not exist: {target}"

        if target.is_file():
            target.unlink()
            return f"File deleted successfully: {target}"

        if target.is_dir():
            try:
                target.rmdir()
                return f"Directory deleted successfully: {target}"
            except OSError:
                return (
                    f"Directory is not empty and was not deleted: {target}"
                )

        return f"Unsupported path type: {target}"

    except Exception as e:
        return f"Error deleting path: {str(e)}"