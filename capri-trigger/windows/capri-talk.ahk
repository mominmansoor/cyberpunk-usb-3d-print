; Capri push-to-talk with LocalFlow  (AutoHotkey v2)
;
; Hold Right Ctrl on its own for 3 seconds -> beep, Capri's typing box opens and
; LocalFlow starts listening. Keep holding and talk. Let go -> LocalFlow pastes your
; words into Capri's box and this script presses Enter to send.
; Tap Right Ctrl or use it in a shortcut (Ctrl+C...) and nothing changes.
;
; Needs: AutoHotkey v2, Capri (Ctrl+Alt+T = typing box), LocalFlow (hold Ctrl+Win = dictate).

#Requires AutoHotkey v2.0
#SingleInstance Force
InstallKeybdHook()
A_MenuMaskKey := "vkE8"      ; stops the Win key from opening the Start menu

HOLD_MS     := 3000          ; how long to hold Right Ctrl before it starts
CAPRI_KEY   := "^!t"         ; Capri: open typing box
PASTE_WAIT  := 15000         ; max ms to wait for LocalFlow to paste
BEEP        := true

global pasted := false
OnClipboardChange(ClipWatch)
ClipWatch(dataType) {
    global pasted := true
}

~RCtrl:: {
    start := A_TickCount
    while GetKeyState("RCtrl", "P") {
        if (A_PriorKey != "RControl")        ; another key was pressed: normal Ctrl use
            return
        if (A_TickCount - start >= HOLD_MS) {
            TalkToCapri()
            return
        }
        Sleep 20
    }
}

TalkToCapri() {
    global pasted
    if BEEP
        SoundBeep 1400, 70
    Send CAPRI_KEY                            ; open Capri's typing box
    Sleep 300
    pasted := false
    Send "{LCtrl down}{LWin down}"            ; hold LocalFlow's dictate keys
    while GetKeyState("RCtrl", "P")          ; ...for as long as you hold Right Ctrl
        Sleep 20
    Send "{LWin up}{LCtrl up}"                ; let go -> LocalFlow transcribes and pastes
    if BEEP
        SoundBeep 900, 50
    start := A_TickCount
    while !pasted && (A_TickCount - start < PASTE_WAIT)
        Sleep 50
    if pasted {
        Sleep 300                             ; let the paste land
        Send "{Enter}"                        ; send it to Capri
    }
}
