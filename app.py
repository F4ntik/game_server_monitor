import sys
import logging
from PyQt6.QtWidgets import QApplication

# Import MainWindow from its new file
from main_window import MainWindow 

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
        filename='app.log',
        filemode='a' 
    )
    logging.info("Application starting.")

    app = QApplication(sys.argv)
    app.setStyle('Fusion') # Apply the Fusion style

    window = MainWindow()
    window.show() # Show the window after instantiation

    exit_code = app.exec()
    logging.info(f"Application exiting with code {exit_code}.")
    sys.exit(exit_code)
