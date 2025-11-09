from State import State
from PySide6.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication()
    state = State()
    state.ui.show()
    app.exec()
