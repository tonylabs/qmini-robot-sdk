#!/usr/bin/env python3
import pygame
import time
import sys
import os

# Set SDL to use dummy video driver (no display required)
os.environ['SDL_VIDEODRIVER'] = 'dummy'

class PS4JoystickTester:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        
        # Check if joystick is connected
        if pygame.joystick.get_count() == 0:
            print("❌ No joystick detected! Please connect your PS4 controller.")
            sys.exit(1)
        
        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        
        print(f"✅ Joystick connected: {self.joystick.get_name()}")
        print(f"📊 Number of axes: {self.joystick.get_numaxes()}")
        print(f"🎮 Number of buttons: {self.joystick.get_numbuttons()}")
        print(f"🧭 Number of hats: {self.joystick.get_numhats()}")
        print("\n" + "="*60)
        print("🎮 PS4 CONTROLLER TEST - Press buttons and move sticks!")
        print("Press Ctrl+C to exit")
        print("="*60 + "\n")
        
        # Button mapping for PS4 controller
        self.button_names = {
            0: "❌ Cross (A)",
            1: "⭕ Circle (B)", 
            2: "🔺 Triangle (Y)",
            3: "🔲 Square (X)",
            4: "L1",
            5: "R1",
            6: "L2",
            7: "R2",
            8: "Share (SELECT)",
            9: "Options (START)",
            10: "PS Button",
            11: "Left Stick Click",
            12: "Right Stick Click"
        }
        
        # Axis mapping
        self.axis_names = {
            0: "Left Stick X",
            1: "Left Stick Y", 
            2: "Right Stick X",
            3: "Right Stick Y",
            4: "L2 Trigger",
            5: "R2 Trigger"
        }
        
        # Hat mapping (D-pad)
        self.hat_directions = {
            (0, 0): "Center",
            (0, 1): "⬆️ Up",
            (1, 1): "↗️ Up-Right", 
            (1, 0): "➡️ Right",
            (1, -1): "↘️ Down-Right",
            (0, -1): "⬇️ Down",
            (-1, -1): "↙️ Down-Left",
            (-1, 0): "⬅️ Left",
            (-1, 1): "↖️ Up-Left"
        }
        
        # Previous states for change detection
        self.prev_buttons = [0] * self.joystick.get_numbuttons()
        self.prev_axes = [0.0] * self.joystick.get_numaxes()
        self.prev_hat = (0, 0)
        
    def format_axis_value(self, value):
        """Format axis value with visual bar"""
        # Normalize to -1.0 to 1.0 range
        normalized = max(-1.0, min(1.0, value))
        
        # Create visual bar (20 characters wide)
        bar_length = 20
        center = bar_length // 2
        pos = int((normalized + 1) * center)
        
        bar = ['-'] * bar_length
        bar[center] = '|'  # Center marker
        if pos != center:
            bar[pos] = '●'
        
        return f"{''.join(bar)} ({normalized:+.3f})"
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def run_test(self):
        """Main test loop"""
        clock = pygame.time.Clock()
        
        try:
            while True:
                pygame.event.pump()
                
                # Check for changes and print only when something changes
                something_changed = False
                
                # Check button changes
                for i in range(self.joystick.get_numbuttons()):
                    current_state = self.joystick.get_button(i)
                    if current_state != self.prev_buttons[i]:
                        something_changed = True
                        if current_state:
                            print(f"🔴 PRESSED:  {self.button_names.get(i, f'Button {i}')}")
                        else:
                            print(f"⚪ RELEASED: {self.button_names.get(i, f'Button {i}')}")
                        self.prev_buttons[i] = current_state
                
                # Check axis changes (with deadzone)
                deadzone = 0.1
                for i in range(self.joystick.get_numaxes()):
                    current_value = self.joystick.get_axis(i)
                    if abs(current_value - self.prev_axes[i]) > deadzone:
                        something_changed = True
                        axis_name = self.axis_names.get(i, f'Axis {i}')
                        print(f"🕹️  {axis_name:15} {self.format_axis_value(current_value)}")
                        self.prev_axes[i] = current_value
                
                # Check hat (D-pad) changes
                if self.joystick.get_numhats() > 0:
                    current_hat = self.joystick.get_hat(0)
                    if current_hat != self.prev_hat:
                        something_changed = True
                        direction = self.hat_directions.get(current_hat, f"({current_hat[0]}, {current_hat[1]})")
                        print(f"🧭 D-Pad: {direction}")
                        self.prev_hat = current_hat
                
                # Add separator line when something changes
                if something_changed:
                    print("-" * 50)
                
                clock.tick(60)  # 60 FPS
                
        except KeyboardInterrupt:
            print("\n\n🛑 Test stopped by user")
            print("Thanks for testing! 👋")
    
    def run_continuous_display(self):
        """Alternative mode: continuous display of all values"""
        clock = pygame.time.Clock()
        
        try:
            while True:
                pygame.event.pump()
                self.clear_screen()
                
                print("🎮 PS4 CONTROLLER LIVE STATUS")
                print("=" * 60)
                print(f"Controller: {self.joystick.get_name()}")
                print("=" * 60)
                
                # Display all axes
                print("\n🕹️  ANALOG STICKS & TRIGGERS:")
                for i in range(self.joystick.get_numaxes()):
                    value = self.joystick.get_axis(i)
                    axis_name = self.axis_names.get(i, f'Axis {i}')
                    print(f"  {axis_name:15} {self.format_axis_value(value)}")
                
                # Display D-pad
                if self.joystick.get_numhats() > 0:
                    hat = self.joystick.get_hat(0)
                    direction = self.hat_directions.get(hat, f"({hat[0]}, {hat[1]})")
                    print(f"\n🧭 D-PAD: {direction}")
                
                # Display buttons
                print("\n🎮 BUTTONS:")
                pressed_buttons = []
                for i in range(self.joystick.get_numbuttons()):
                    if self.joystick.get_button(i):
                        button_name = self.button_names.get(i, f'Button {i}')
                        pressed_buttons.append(button_name)
                
                if pressed_buttons:
                    print(f"  PRESSED: {', '.join(pressed_buttons)}")
                else:
                    print("  No buttons pressed")
                
                print("\n" + "=" * 60)
                print("Press Ctrl+C to exit")
                
                clock.tick(30)  # 30 FPS for continuous display
                
        except KeyboardInterrupt:
            print("\n\n🛑 Test stopped by user")
            print("Thanks for testing! 👋")

def main():
    print("🎮 PS4 Controller Test Utility")
    print("Choose test mode:")
    print("1. Event-based (shows changes only)")
    print("2. Continuous display (live status)")
    
    try:
        choice = input("\nEnter choice (1 or 2): ").strip()
        
        tester = PS4JoystickTester()
        
        if choice == "2":
            print("\nStarting continuous display mode...")
            time.sleep(1)
            tester.run_continuous_display()
        else:
            print("\nStarting event-based mode...")
            print("Move sticks, press buttons, use D-pad to see output\n")
            tester.run_test()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()