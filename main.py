import sys
from ClassRawEdit import RawEditor

from PyQt5.QtWidgets import QApplication


def main():
    app = QApplication(sys.argv)
    editor = RawEditor()
    editor.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
