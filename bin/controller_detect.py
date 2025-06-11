#!/usr/bin/env python3
import pygame
import sys

def detect_controllers():
    pygame.init()
    pygame.joystick.init()
    
    print("🔍 Scanning for controllers...")
    print(f"Number of joysticks detected: {pygame.joystick.get_count()}")
    
    if pygame.joystick.get_count() == 0:
        print("❌ No controllers found!")
        print("\n📋 Troubleshooting steps:")
        print("1. Make sure controller is connected (USB or Bluetooth)")
        print("2. Try reconnecting the controller")
        print("3. Check if controller works in other applications")
        print("4. Restart the script after connecting")
        return False
    
    for i in range(pygame.joystick.get_count()):
        joystick = pygame.joystick.Joystick(i)
        joystick.init()
        print(f"\n✅ Controller {i}:")
        print(f"   Name: {joystick.get_name()}")
        print(f"   Axes: {joystick.get_numaxes()}")
        print(f"   Buttons: {joystick.get_numbuttons()}")
        print(f"   Hats: {joystick.get_numhats()}")
    
    return True

if __name__ == "__main__":
    if detect_controllers():
        print("\n🎮 Controllers detected! You can now run joystick_test.py")
    else:
        print("\n🔧 Please fix controller connection and try again")
    
    pygame.quit()