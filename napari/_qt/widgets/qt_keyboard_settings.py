import re
from collections import OrderedDict

from qtpy.QtCore import QEvent, QPoint, Qt, Signal
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QItemDelegate,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...layers import Image, Labels, Points, Shapes, Surface, Vectors
from ...utils.action_manager import action_manager
from ...utils.interactions import Shortcut
from ...utils.settings import SETTINGS
from ...utils.translations import trans
from ..dialogs.qt_message_dialogs import ConfirmDialog
from ..qt_resources import get_stylesheet

KEY_SUBS = {'Ctrl': 'Control'}


class ShortcutEditor(QDialog):
    """ """

    valueChanged = Signal(dict)
    ALL_ACTIVE_KEYBINDINGS = trans._('Viewer key bindings')

    def __init__(
        self,
        # viewer,
        # key_map_handler,
        parent: QWidget = None,
        description: str = "",
        value: dict = None,
    ):

        super().__init__(parent=parent)

        self._qsequences = list()
        self._new_keys = ''

        print('ShortcutOverride', QEvent.ShortcutOverride)
        print('keypress', QEvent.KeyPress)
        print('shortcut', QEvent.Shortcut)

        layers = [
            Image,
            Labels,
            Points,
            Shapes,
            Surface,
            Vectors,
        ]

        self.key_bindings_strs = OrderedDict()

        # widgets
        self.layer_combo_box = QComboBox(self)
        self._label = QLabel(self)
        self._table = QTableWidget(self)

        self._table.setShowGrid(False)

        # Set up buttons
        self._restore_button = QPushButton(trans._("Reset All Keybindings"))

        # set up
        # all actions
        all_actions = action_manager._actions.copy()
        self.key_bindings_strs[self.ALL_ACTIVE_KEYBINDINGS] = []

        for layer in layers:
            if len(layer.class_keymap) == 0:
                actions = []
            else:
                actions = action_manager._get_layer_actions(layer)
                for name, action in actions.items():
                    all_actions.pop(name)
            self.key_bindings_strs[f"{layer.__name__} layer"] = actions
        # left over actions can go here.
        self.key_bindings_strs[self.ALL_ACTIVE_KEYBINDINGS] = all_actions

        self.layer_combo_box.addItems(list(self.key_bindings_strs))
        self.layer_combo_box.activated[str].connect(self._set_table)
        self.layer_combo_box.setCurrentText(self.ALL_ACTIVE_KEYBINDINGS)
        self._set_table()
        self._label.setText("Group")

        self._restore_button.clicked.connect(self.restore_defaults)

        # layout

        hlayout1 = QHBoxLayout()

        hlayout1.addWidget(self._label)
        hlayout1.addWidget(self.layer_combo_box)
        hlayout1.setContentsMargins(0, 0, 0, 0)
        hlayout1.setSpacing(20)
        hlayout1.addStretch(0)

        hlayout2 = QHBoxLayout()
        hlayout2.addLayout(hlayout1)
        hlayout2.addWidget(self._restore_button)

        layout = QVBoxLayout()
        layout.addLayout(hlayout2)
        layout.addWidget(self._table)

        self.setLayout(layout)

    # def event(self, event):
    #     """Qt method override."""
    #     # We reroute all ShortcutOverride events to our keyPressEvent and block
    #     # any KeyPress and Shortcut event. This allows to register default
    #     # Qt shortcuts for which no key press event are emitted.
    #     # See spyder-ide/spyder/issues/10786.
    #     # spyder code

    #     if event.type() == QEvent.ShortcutOverride:
    #         print('check 1')
    #         self.keyPressEvent(event)
    #         return True
    #     elif event.type() in [QEvent.KeyPress, QEvent.Shortcut]:
    #         print('check 2', event.key())
    #         return True
    #     else:
    #         print('check 2b')
    #         return super().event(event)

    def keyPressEvent(self, event):
        """Qt method override."""

        event_key = event.key()
        if not event_key or event_key == Qt.Key_unknown:
            return
        if len(self._qsequences) == 4:
            # QKeySequence accepts a maximum of 3 different sequences.
            return
        if event_key in [
            Qt.Key_Control,
            Qt.Key_Shift,
            Qt.Key_Alt,
            Qt.Key_Meta,
            Qt.Key_Return,
            Qt.Key_Tab,
        ]:
            # do we want to be able to set these?
            return

        translator = ShortcutTranslator()
        event_keyseq = translator.keyevent_to_keyseq(event)
        # print('event_keyseq', event_keyseq)
        # print('event to string', event_keyseq.toString())
        event_keystr = event_keyseq.toString(QKeySequence.PortableText)
        # print(len(event_keystr))
        # print('event_keystr', event_keystr)

        self._qsequences.append(event_keystr)

        if len(self._qsequences[-1]) > 0:
            item1 = self._table.currentItem()

            parsed = re.split('[-(?=.+)]', self._qsequences[-1])
            keys = []
            for val in parsed:
                if val in KEY_SUBS.keys():
                    keys.append(KEY_SUBS[val])
                else:
                    keys.append(val)

            keys = '-'.join(keys)
            self._new_keys = keys
            print('setting key')
            item1.setText(Shortcut(keys).platform)
            print('done setting')
            return

    def restore_defaults(self):
        """Launches dialog to confirm restore choice."""
        self._reset_dialog = ConfirmDialog(
            parent=self,
            text=trans._(
                "Are you sure you want to restore default shortcuts?"
            ),
        )
        self._reset_dialog.valueChanged.connect(self._reset_shortcuts)
        self._reset_dialog.exec_()

    def _reset_shortcuts(self, event=None):
        # event is True if the user confirmed reset shortcuts
        if event is True:
            SETTINGS.reset(sections=['shortcuts'])
            for action, shortcuts in SETTINGS.shortcuts.shortcuts.items():
                action_manager.unbind_shortcut(action)
                for shortcut in shortcuts:
                    action_manager.bind_shortcut(action, shortcut)

            self._set_table(layer_str=self.layer_combo_box.currentText())

    def _set_table(self, layer_str=''):

        # keep track of what is in each column
        self._action_name_col = 0
        self._icon_col = 1
        self._shortcut_col = 2
        self._action_col = 3

        header_strs = ['', '', '', '']
        header_strs[self._action_name_col] = 'Action'
        header_strs[self._shortcut_col] = 'Keybinding'

        if layer_str == '':
            layer_str = self.ALL_ACTIVE_KEYBINDINGS

        try:
            self._table.cellChanged.disconnect(self._set_keybinding)
        except TypeError:
            pass

        self._table.clearContents()

        self._table.horizontalHeader().setStretchLastSection(True)
        # self._table.horizontalHeader().setSectionResizeMode(
        #     QHeaderView.Stretch
        # )
        self._table.horizontalHeader().setStyleSheet(
            'border-bottom: 2px solid white;'
        )

        # self._table.resizeColumnsToContents()

        actions = self.key_bindings_strs[layer_str]

        if len(actions) > 0:

            self._table.setRowCount(len(actions))
            self._table.setColumnCount(4)
            self._table.setItemDelegateForColumn(
                self._shortcut_col, ShortcutDelegate(self._table)
            )
            self._table.setHorizontalHeaderLabels(header_strs)
            self._table.verticalHeader().setVisible(False)

            self._table.setColumnHidden(self._action_col, True)
            self._table.setColumnWidth(self._action_name_col, 250)
            self._table.setColumnWidth(self._shortcut_col, 200)
            self._table.setColumnWidth(self._icon_col, 50)

            for row, (action_name, action) in enumerate(actions.items()):
                shortcuts = action_manager._shortcuts.get(action_name, [])
                item = QTableWidgetItem(action.description)

                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                # item.setStyleSheet('border-top: 1px solid white; border-bottom: 1px solid white;')

                self._table.setItem(row, self._action_name_col, item)
                item_shortcut = QTableWidgetItem(
                    Shortcut(list(shortcuts)[0]).platform if shortcuts else ""
                )

                self._table.setItem(row, self._shortcut_col, item_shortcut)

                item_action = QTableWidgetItem(action_name)
                # action_name is stored in the table to use later, but is not shown on dialog.
                self._table.setItem(row, self._action_col, item_action)

            self._table.cellChanged.connect(self._set_keybinding)
        else:
            # no actions-- display that.
            self._table.setRowCount(1)
            self._table.setColumnCount(4)
            self._table.setHorizontalHeaderLabels(header_strs)
            self._table.verticalHeader().setVisible(False)

            self._table.setColumnHidden(self._action_col, True)
            item = QTableWidgetItem('No key bindings')
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(0, 0, item)

    def _set_keybinding(self, row, col):

        if col == self._shortcut_col:
            # event is the index of the event.
            current_layer_text = self.layer_combo_box.currentText()
            layer_actions = self.key_bindings_strs[current_layer_text]
            actions_all = layer_actions.copy()
            if current_layer_text is not self.ALL_ACTIVE_KEYBINDINGS:
                viewer_actions = self.key_bindings_strs[
                    self.ALL_ACTIVE_KEYBINDINGS
                ]

                actions_all.update(viewer_actions)

            # get the current item from shortcuts column
            item1 = self._table.currentItem()
            new_shortcut = item1.text()
            new_shortcut = new_shortcut[0].upper() + new_shortcut[1:]

            # get the action name
            current_action = self._table.item(row, self._action_col).text()

            replace = True
            for row1, (action_name, action) in enumerate(actions_all.items()):
                shortcuts = action_manager._shortcuts.get(action_name, [])

                # shortcuts = [kb.lower() for kb in shortcuts]

                if self._new_keys != '':
                    new_shortcut = self._new_keys
                    self._new_keys = ''

                if new_shortcut in shortcuts:
                    # shortcut is here (either same action or not), don't replace in settings.
                    replace = False
                    if action_name != current_action:
                        # the shortcut is saved to a different action, show message.
                        # pop up window for warning.
                        message = trans._(
                            "The keybinding <b>{new_shortcut}</b>  "
                            + "is already assigned to <b>{action_description}</b>; change or clear "
                            + "that shortcut before assigning <b>{new_shortcut}</b> to this one.",
                            new_shortcut=new_shortcut,
                            action_description=action.description,
                        )

                        delta_y = 105
                        delta_x = 10
                        global_point = self.mapToGlobal(
                            QPoint(
                                self._table.columnViewportPosition(col)
                                + delta_x,
                                self._table.rowViewportPosition(row) + delta_y,
                            )
                        )

                        self._warn_dialog = KeyBindWarnPopup(
                            text=message,
                        )
                        self._warn_dialog.move(global_point)

                        self._warn_dialog.resize(
                            250, self._warn_dialog.sizeHint().height()
                        )

                        self._warn_dialog._message.resize(
                            200, self._warn_dialog._message.sizeHint().height()
                        )

                        self.warning_indicator = QLabel(self)
                        self.warning_indicator.setObjectName("error_label")

                        self.warning_indicator2 = QLabel(self)
                        self.warning_indicator2.setObjectName("error_label")

                        self._table.setCellWidget(
                            row, self._icon_col, self.warning_indicator
                        )
                        self._table.setCellWidget(
                            row1, self._icon_col, self.warning_indicator2
                        )

                        self._warn_dialog.exec_()

                        # get the original shortcut
                        current_shortcuts = list(
                            action_manager._shortcuts.get(current_action, {})
                        )
                        print('current', current_shortcuts)
                        print(len(current_shortcuts))
                        if len(current_shortcuts) > 0:
                            print('check 3', current_shortcuts[0])
                            item1.setText(current_shortcuts[0])

                        else:

                            item1.setText("")

                        self._table.setCellWidget(
                            row, self._icon_col, QLabel("")
                        )
                        self._table.setCellWidget(
                            row1, self._icon_col, QLabel("")
                        )

                        break
                    else:
                        # this one was here, need to re-format in case its not done
                        csc = Shortcut(new_shortcut).platform
                        self._new_keys = new_shortcut
                        item1.setText(csc)
            if replace is True:

                # this shortcut is not taken, can set it and save in settings
                # how are we doing this? saving in settings and then that triggers to update the action manager?
                # right now I'm updating the action manager, and settings will be saved after a trigger as with
                # all the other widgets.

                #  Bind new shortcut to the action manager
                action_manager.unbind_shortcut(current_action)

                if new_shortcut != "":
                    action_manager.bind_shortcut(current_action, new_shortcut)

                    new_value_dict = {current_action: [new_shortcut]}

                    # update the symbols in the text
                    sc = Shortcut(new_shortcut).platform
                    item1.setText(sc)
                else:

                    if action_manager._shortcuts[current_action] != "":
                        new_value_dict = {current_action: [""]}

                if new_value_dict:

                    self.setChangedValue(new_value_dict)
                    self.valueChanged.emit(new_value_dict)

    def setChangedValue(self, value):
        self._changed_value = value

    def value(self):
        # consult action manager for current actions.

        # return self._changed_value
        value = {}

        for row, (action_name, action) in enumerate(
            action_manager._actions.items()
        ):
            shortcuts = action_manager._shortcuts.get(action_name, [])
            value[action_name] = list(shortcuts)

        return value


class KeyBindWarnPopup(QDialog):
    """Dialog to inform user that shortcut is already assigned."""

    # valueChanged = Signal()
    def __init__(
        self,
        parent=None,
        text: str = "",
    ):
        super().__init__(parent)

        self.setWindowFlags(Qt.FramelessWindowHint)

        # Set up components
        self._message = QLabel()
        self._xbutton = QPushButton('x', self)
        self._xbutton.setFixedSize(20, 20)

        # Widget set up
        self._message.setText(text)
        self._message.setWordWrap(True)
        self._xbutton.clicked.connect(self._close)
        self._xbutton.setStyleSheet("background-color: rgba(0, 0, 0, 0);")

        # Layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self._message)

        # self._xbutton.move(0, 0)

        self.setLayout(main_layout)

        self.setStyleSheet(get_stylesheet(SETTINGS.appearance.theme))

        # self.setWindowFlags(Qt.FramelessWindowHint)

    def _close(self):

        self.close()


class ShortcutDelegate(QItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, QWidget, QStyleOptionViewItem, QModelIndex):
        self._editor = EditorWidget(QWidget)
        self._editor.setFocusProxy(self._editor._edit)
        return self._editor

    def setEditorData(self, widget, QModelIndex):
        text = QModelIndex.model().data(QModelIndex, Qt.EditRole)
        widget.setText(str(text) if text else "")
        widget._edit.setFocus()

    def updateEditorGeometry(self, QWidget, QStyleOptionViewItem, QModelIndex):
        QWidget.setGeometry(QStyleOptionViewItem.rect)

    def setModelData(self, widget, QAbstractItemModel, QModelIndex):
        text = widget.text()
        QAbstractItemModel.setData(QModelIndex, text, Qt.EditRole)


class EditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._edit = QLineEdit()
        # remove_button = QToolButton()
        # add_button = QToolButton()
        layout = QHBoxLayout()
        layout.addWidget(self._edit, 5)
        # layout.addWidget(add_button, 1)
        # layout.addWidget(remove_button, 1)
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)

    def setText(self, text):
        self._edit.setText(text)

    def text(self):
        return self._edit.text() or ""


class ShortcutTranslator(QKeySequenceEdit):
    """
    A QKeySequenceEdit that is not meant to be shown and is used only
    to convert QKeyEvent into QKeySequence. To our knowledge, this is
    the only way to do this within the Qt framework, because the code that does
    this in Qt is protected. Porting the code to Python would be nearly
    impossible because it relies on low level and OS-dependent Qt libraries
    that are not public for the most part.  (Notes from Spyder repo)
    """

    def __init__(self):
        super().__init__()
        self.hide()

    def keyevent_to_keyseq(self, event):
        """Return a QKeySequence representation of the provided QKeyEvent."""
        print(event)
        self.keyPressEvent(event)
        event.accept()
        print('keyseq!!!!', self.keySequence().toString())
        return self.keySequence()

    def keyReleaseEvent(self, event):
        """Qt Override"""
        return False

    def timerEvent(self, event):
        """Qt Override"""
        return False

    def event(self, event):
        """Qt Override"""
        return False
