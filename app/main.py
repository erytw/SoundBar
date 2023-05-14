import sys
import os

import sqlite3
import audioplayer

from PyQt5.QtGui import QPixmap
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QWidget, QFileDialog

from interface import *

if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.AA_EnableHighDpiScaling, True)

if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)


# Globals
ProfileId = 0
ok = True


class ProfileSelection(QDialog, Ui_ProfileSelection):
    def __init__(self, con, cur):
        super().__init__()
        self.setupUi(self)
        self.con = con
        self.cur = cur
        self.btn_del.clicked.connect(self.deleteProfile)
        self.btn_new.clicked.connect(self.createProfile)
        self.btn_open.clicked.connect(self.openProfile)
        self.update()

    def update(self):
        self.combo.clear()
        data = [x[0] for x in self.cur.execute(
            """SELECT Profile.Title FROM Profile""").fetchall()]
        self.combo.addItems(data)

    def deleteProfile(self):
        try:
            id = self.cur.execute(
                """
                SELECT Profile.ProfileId FROM Profile
                WHERE Profile.Title == ?
                """,
                (self.combo.currentText(), )
            ).fetchone()[0]
            self.cur.execute(
                "DELETE FROM Profile WHERE Profile.ProfileId == ?", (id,))
            self.cur.execute(
                "DELETE FROM Audio WHERE Audio.ProfileId == ?", (id,))
            self.con.commit()
            self.update()
        except Exception:
            return

    def createProfile(self):
        NewProfile(self.con, self.cur).exec()
        self.update()
        self.combo.setCurrentIndex(self.combo.count() - 1)

    def openProfile(self):
        if self.combo.count() == 0:
            return
        global ProfileId
        ProfileId = self.cur.execute(
            """
            SELECT Profile.ProfileId FROM Profile
            WHERE Profile.Title = ?
            """,
            (self.combo.currentText(),),
        ).fetchone()[0]
        self.close()


class NewProfile(QDialog, Ui_NewProfile):
    def __init__(self, con, cur):
        super().__init__()
        self.setupUi(self)
        self.con = con
        self.cur = cur
        self.btn_save.clicked.connect(self.saveProfile)
        self.btn_back.clicked.connect(self.close)

    def saveProfile(self):
        txt = self.line.text()
        if len(txt) == 0:
            return
        self.cur.execute("INSERT INTO Profile(Title) VALUES(?)", (txt,))
        self.con.commit()
        self.close()


class ProfileInterface(QMainWindow, Ui_ProfileInterface):
    def __init__(self, db="db.sqlite"):
        global ok
        super().__init__()
        self.setupUi(self)
        self.btn_add_audio.clicked.connect(self.addAudio)
        self.btn_del_audio.clicked.connect(self.delAudio)
        self.btn_new_sequence.clicked.connect(self.addSequence)
        self.btn_del_sequence.clicked.connect(self.delSequence)
        self.btn_append.clicked.connect(self.addSequenceAudio)
        self.btn_pop.clicked.connect(self.delSequenceAudio)
        self.player_btn.clicked.connect(self.startPlayer)
        self.combo.currentTextChanged.connect(self.updateSequenceList)
        self.con = sqlite3.connect(db)
        self.cur = self.con.cursor()
        f_in = open("startup.txt", "rt", encoding="utf8")
        data = int(f_in.read()[0])
        if data == 1:
            ok = False
            f_out = open("startup.txt", "w", encoding="utf8")
            print(0, file=f_out)
            f_out.close()
            self.hide()
            Hello().exec()
        if not ok:
            self.close()
        f_in.close()
        ProfileSelection(self.con, self.cur).exec()
        self.setWindowTitle(self.cur.execute(
            """
                SELECT Profile.Title FROM Profile
                WHERE Profile.ProfileId == ?
            """,
            (ProfileId,)
        ).fetchone()[0])
        self.update_audio()
        self.updateCombo()
        self.updateSequenceList()

    def update_audio(self):
        self.audio_list.clear()
        table_data = self.cur.execute(
            """
            SELECT Audio.Title FROM Audio
            WHERE Audio.ProfileId == ?
            """,
            (ProfileId,)
        ).fetchall()
        self.audioList = [x[0] for x in self.cur.execute(
            """
                SELECT Audio.AudioId FROM Audio
                INNER JOIN Profile
                ON Audio.ProfileId = Profile.ProfileId
            """
        ).fetchall()]
        table_data = [x[0] for x in table_data]
        if len(table_data) > 0:
            self.audio_list.addItems(table_data)

    def updateSequenceList(self):
        self.sequence_list.clear()
        try:
            self.SequenceId = self.cur.execute(
                """
                    SELECT Sequence.SequenceId FROM Sequence
                    WHERE Sequence.Title == ?
                """, (self.combo.currentText(), )
            ).fetchone()[0]
            self.currentSequence = self.cur.execute(
                """
                    SELECT Audio.Title, Audio.Path FROM Audio
                    INNER JOIN AudioSequence
                    ON Audio.AudioId = AudioSequence.AudioId
                    WHERE AudioSequence.SequenceId = ?
                    ORDER BY AudioSequence.i
                """, (self.SequenceId, )
            ).fetchall()
            self.iMax = len(self.currentSequence)
            self.sequence_list.clear()
            table_data = [data[0] for data in self.currentSequence]
            if len(table_data) > 0:
                self.sequence_list.addItems(table_data)
        except Exception:
            return

    def addSequenceAudio(self):
        self.cur.execute(
            """
                INSERT INTO AudioSequence(AudioId, i, SequenceId)
                VALUES(?, ?, ?)
            """,
            (self.audioList[self.audio_list.currentRow()],
             self.iMax, self.SequenceId)
        )
        self.con.commit()
        self.updateSequenceList()

    def delSequenceAudio(self):
        self.cur.execute(
            """
                DELETE FROM AudioSequence
                WHERE AudioSequence.SequenceId == ? AND AudioSequence.i == ?
            """,
            (self.SequenceId, self.iMax - 1)
        )
        self.con.commit()
        self.updateSequenceList()

    def updateCombo(self):
        self.combo.clear()
        data = [x[0] for x in self.cur.execute(
            """
            SELECT Sequence.Title FROM Sequence
            WHERE Sequence.ProfileId == ?
            """,
            (ProfileId,)
        ).fetchall()]
        self.combo.addItems(data)

    def addAudio(self):
        NewAudio(self.con, self.cur).exec()
        self.update_audio()

    def delAudio(self):
        if not self.audio_list.currentItem():
            return
        self.cur.execute(
            """
            DELETE FROM Audio
            WHERE Audio.ProfileId = ? AND Audio.Title = ?
            """,
            (ProfileId, self.audio_list.currentItem().text())
        )
        self.cur.execute(
            """
            DELETE FROM AudioSequence
            WHERE AudioSequence.AudioId in (
                SELECT Audio.AudioId FROM Audio
                WHERE Audio.ProfileId = ? AND Audio.Title = ?
            )
            """,
            (ProfileId, self.audio_list.currentItem().text())
        )
        self.con.commit()
        self.update_audio()

    def addSequence(self):
        NewSequence(self.con, self.cur).exec()
        self.updateCombo()
        self.combo.setCurrentIndex(self.combo.count() - 1)

    def delSequence(self):
        try:
            self.cur.execute(
                "DELETE FROM AudioSequence WHERE AudioSequence.SequenceId == ?", (self.SequenceId,))
            self.cur.execute(
                "DELETE FROM Sequence WHERE Sequence.SequenceId == ?", (self.SequenceId,))
            self.con.commit()
            self.updateCombo()
        except Exception:
            return

    def startPlayer(self):
        nw = Player(self.currentSequence)
        nw.exec()
        nw.stop()


class NewAudio(QDialog, Ui_NewAudio):
    def __init__(self, con, cur):
        super().__init__()
        self.setupUi(self)
        self.con = con
        self.cur = cur
        self.btn_select_path.clicked.connect(self.getPath)
        self.btn_cancel.clicked.connect(self.close)
        self.btn_save.clicked.connect(self.saveAudio)

    def getPath(self):
        self.audio_path.setText(QFileDialog.getOpenFileName(
            self, 'Выбрать аудиофайл', '', "Аудио (*.mp3);;Все файлы (*)")[0])

    def saveAudio(self):
        path = self.audio_path.text()
        title = self.audio_title.text()
        if not (os.path.isfile(path)) or len(title) == 0:
            return
        self.cur.execute(
            """
            INSERT INTO Audio(Title, Path, ProfileId)
            VALUES(?,?,?)
            """,
            (title, path, ProfileId)
        )
        self.con.commit()
        self.close()


class NewSequence(QDialog, Ui_NewSequence):
    def __init__(self, con, cur):
        super().__init__()
        self.setupUi(self)
        self.con = con
        self.cur = cur
        self.btn_save.clicked.connect(self.saveProfile)
        self.btn_back.clicked.connect(self.close)

    def saveProfile(self):
        txt = self.line.text()
        if len(txt) == 0:
            return
        self.cur.execute(
            "INSERT INTO Sequence(Title, ProfileId) VALUES(?, ?)",
            (txt, ProfileId)
        )
        self.con.commit()
        self.close()


class Player(QDialog, Ui_Player):
    def __init__(self, data):
        super().__init__()
        self.setupUi(self)
        self.playing = False
        self.data = data
        self.i = 0
        self.current_snd = audioplayer.AudioPlayer(self.data[self.i][1])
        self.current_snd.play(loop=True)
        self.current_snd.pause()
        self.update_songs()
        self.pause_btn.clicked.connect(self.pauseresume)
        self.next_btn.clicked.connect(self.forward)
        self.prev_btn.clicked.connect(self.backwards)

    def pauseresume(self):
        self.playing ^= True
        if self.playing:
            self.pause_btn.setText("⏸")
            self.current_snd.resume()
        else:
            self.pause_btn.setText("⏵")
            self.current_snd.pause()

    def update_songs(self):
        self.prev.clear()
        self.now_playing.clear()
        self.next.clear()
        if (self.i > 0):
            self.prev.setText(self.data[self.i - 1][0])
        self.now_playing.setText(self.data[self.i][0])
        if (self.i < len(self.data) - 1):
            self.next.setText(self.data[self.i + 1][0])

    def forward(self):
        if self.i >= len(self.data) - 1:
            return
        self.i += 1
        self.current_snd.close()
        self.current_snd = audioplayer.AudioPlayer(self.data[self.i][1])
        self.current_snd.play(loop=True)
        if not self.playing:
            self.current_snd.pause()
        self.update_songs()

    def backwards(self):
        if self.i <= 0:
            return
        self.i -= 1
        self.current_snd.close()
        self.current_snd = audioplayer.AudioPlayer(self.data[self.i][1])
        self.current_snd.play(loop=True)
        if not self.playing:
            self.current_snd.pause()
        self.update_songs()

    def stop(self):
        self.current_snd.close()


class Hello(QDialog, Ui_Hello):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.pixmap = QPixmap("resources/kotik.gif")
        self.image.setPixmap(self.pixmap)
        self.btn_hello.clicked.connect(self.stop)
        self.audio = audioplayer.AudioPlayer("resources/privet.mp3")
        self.audio.play(loop=True)

    def stop(self):
        global ok
        ok = True
        self.audio.close()
        self.close()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ProfileInterface()
    ex.show()
    sys.exit(app.exec_())
