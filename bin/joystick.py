import os
import pygame
import json

# Set SDL to use dummy video driver (no display required)
os.environ['SDL_VIDEODRIVER'] = 'dummy'

# -----------------------------------------------------------------------------
# Sony PS5 DualSense mapping (pygame 2.1 / SDL 2.0.20, Linux hid-generic).
#
# Verified empirically on the Qmini robot with scripts/pair_ps5_controller.sh.
# The controller enumerates as "DualSense Wireless Controller" with 6 axes,
# 14 buttons, 1 hat. Button/axis indices below are what SDL reports:
#
#   Axes:                              Buttons:
#     0  Left  stick X  (right +)        0  Square   ▢       7  R2 (digital)
#     1  Left  stick Y  (down  +)        1  Cross    ✕       8  Create (Share)
#     2  Right stick X  (right +)        2  Circle   ◯       9  Options
#     3  L2 trigger     (rest -1..+1)    3  Triangle △      10  L3
#     4  R2 trigger     (rest -1..+1)    4  L1             11  R3
#     5  Right stick Y  (down  +)        5  R1             12  PS
#                                        6  L2 (digital)   13  Touchpad
#     Hat 0: D-pad, (x, y) with up/right = +1
#
# The face buttons are exposed to the SDK by POSITION (matching the original
# Xbox A/B/X/Y layout the C++ side expects), not by Sony label:
#     butA = bottom = Cross ✕     butX = left  = Square ▢
#     butB = right  = Circle ◯    butY = top   = Triangle △
# -----------------------------------------------------------------------------

# pygame axis indices
AX_LX, AX_LY = 0, 1
AX_RX, AX_RY = 2, 5
AX_L2, AX_R2 = 3, 4

# pygame button indices
BTN_SQUARE, BTN_CROSS, BTN_CIRCLE, BTN_TRIANGLE = 0, 1, 2, 3
BTN_L1, BTN_R1, BTN_L2, BTN_R2 = 4, 5, 6, 7
BTN_CREATE, BTN_OPTIONS, BTN_L3, BTN_R3, BTN_PS, BTN_TOUCHPAD = 8, 9, 10, 11, 12, 13


class JoyStick:
    # 按键定义 (values exposed to the C++ JoystickReader via read_joystick())
    LaxiX = 0.0    # 左摇杆X轴, axis[0]
    LaxiY = 0.0    # 左摇杆Y轴, axis[1]
    RaxiX = 0.0    # 右摇杆X轴, axis[2]
    RaxiY = 0.0    # 右摇杆Y轴, axis[5]
    hatX = 0       # 方向键X轴, hat[0]
    hatY = 0       # 方向键Y轴, hat[1]
    butA = 0       # A键 = Cross ✕,    button[1]
    butB = 0       # B键 = Circle ◯,   button[2]
    butX = 0       # X键 = Square ▢,   button[0]
    butY = 0       # Y键 = Triangle △, button[3]
    L1 = 0         # L1键, button[4]
    R1 = 0         # R1键, button[5]
    L2 = 0         # L2键, button[6]
    R2 = 0         # R2键, button[7]
    SELECT = 0     # SELECT键 = Create/Share, button[8]
    START = 0      # START键 = Options,       button[9]

    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        self.joystick = None

    def initjoystick(self):
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError("No joystick detected")
        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()

    def _button(self, idx):
        """Safe button read (returns 0 if the index is out of range)."""
        return self.joystick.get_button(idx) if idx < self.joystick.get_numbuttons() else 0

    def _axis(self, idx):
        return self.joystick.get_axis(idx) if idx < self.joystick.get_numaxes() else 0.0

    def getjoystickstates(self):
        # (Re)acquire the joystick in case it was reconnected.
        if self.joystick is None or pygame.joystick.get_count() == 0:
            if pygame.joystick.get_count() == 0:
                return
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()

        # Pump the SDL event queue so get_axis/get_button return fresh values,
        # then read the full controller state directly (robust to which event
        # types fired this cycle).
        pygame.event.pump()

        self.LaxiX = self._axis(AX_LX)
        self.LaxiY = self._axis(AX_LY)
        self.RaxiX = self._axis(AX_RX)
        self.RaxiY = self._axis(AX_RY)

        if self.joystick.get_numhats() > 0:
            hat = self.joystick.get_hat(0)
            self.hatX, self.hatY = hat[0], hat[1]
        else:
            self.hatX, self.hatY = 0, 0

        # Face buttons mapped by position (see header).
        self.butA = self._button(BTN_CROSS)      # bottom
        self.butB = self._button(BTN_CIRCLE)     # right
        self.butX = self._button(BTN_SQUARE)     # left
        self.butY = self._button(BTN_TRIANGLE)   # top

        self.L1 = self._button(BTN_L1)
        self.R1 = self._button(BTN_R1)
        # L2/R2: use the digital button; fall back to the analog trigger axis
        # (rest -1, pressed +1) in case the button index is absent.
        self.L2 = 1 if (self._button(BTN_L2) or self._axis(AX_L2) > 0.0) else 0
        self.R2 = 1 if (self._button(BTN_R2) or self._axis(AX_R2) > 0.0) else 0

        self.SELECT = self._button(BTN_CREATE)   # Create / Share
        self.START = self._button(BTN_OPTIONS)   # Options

    def display(self):
        print('================')
        print('Axies:')
        print('LaxiX: {}'.format(self.LaxiX))
        print('LaxiY: {}'.format(self.LaxiY))
        print('RaxiX: {}'.format(self.RaxiX))
        print('RaxiY: {}'.format(self.RaxiY))
        print('----------------')
        print('Hat:')
        print('hatX: {}'.format(self.hatX))
        print('hatY: {}'.format(self.hatY))
        print('----------------')
        print('button:')
        print('butA: {}'.format(self.butA))
        print('butB: {}'.format(self.butB))
        print('butX: {}'.format(self.butX))
        print('butY: {}'.format(self.butY))
        print('L1: {}'.format(self.L1))
        print('R1: {}'.format(self.R1))
        print('L2: {}'.format(self.L2))
        print('R2: {}'.format(self.R2))
        print('SELECT: {}'.format(self.SELECT))
        print('START: {}'.format(self.START))
        print('================')


joy = JoyStick()


def init_joystick():
    global joy
    joy.initjoystick()


def get_joystick_count():
    pygame.init()
    pygame.joystick.init()
    return pygame.joystick.get_count()


def read_joystick():
    global joy
    joy.getjoystickstates()

    result = {
        "LaxiX": joy.LaxiX,
        "LaxiY": joy.LaxiY,
        "RaxiX": joy.RaxiX,
        "RaxiY": joy.RaxiY,
        "hatX": joy.hatX,
        "hatY": joy.hatY,
        "butA": joy.butA,
        "butB": joy.butB,
        "butX": joy.butX,
        "butY": joy.butY,
        "L1": joy.L1,
        "R1": joy.R1,
        "L2": joy.L2,
        "R2": joy.R2,
        "SELECT": joy.SELECT,
        "START": joy.START,
    }

    return json.dumps(result)
