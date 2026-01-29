from textual.app import App, ComposeResult 
from textual.widgets import Header, Input, Static, DirectoryTree

class FileInput(Static):
    BORDER_TITLE = "To compile ..."

    def compose(self) -> ComposeResult:
        self.picker = DirectoryTree("./")
        yield self.picker

class CompilerGUI(App[None]):
    CSS_PATH = "default.tcss"
    TITLE = "CBLang compiler GUI"

    def on_mount(self) -> None:
        self.theme = "tokyo-night"

    def compose(self) -> ComposeResult:
        yield Header()
        yield FileInput()
    
    def on_button_pressed(self) -> None:
        self.exit()

if __name__ == "__main__":
    app = CompilerGUI()
    app.run()