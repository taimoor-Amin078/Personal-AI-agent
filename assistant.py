import speech_recognition as sr
import pyttsx3
from google import genai
import pywhatkit
import os
import subprocess
import time
import json
import docx

# --- Configuration ---
# TODO: Replace with your actual Gemini API Key
GEMINI_API_KEY = "paste your key here!"

# --- Address Book ---
# Add your contacts here (name: phone number with country code)
CONTACTS = {
    "john": "+923000000000",
    "alice": "+923111111111"
}

# Configure Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# Initialize Text-to-Speech engine
engine = pyttsx3.init()
voices = engine.getProperty('voices')
# Try to set a female voice if available, usually index 1
if len(voices) > 1:
    engine.setProperty('voice', voices[1].id)

def speak(text):
    print(f"\nAssistant: {text}\n")
    engine.say(text)
    engine.runAndWait()

def listen():
    try:
        import sounddevice as sd
        import scipy.io.wavfile as wav
        import numpy as np
        
        fs = 44100  # Sample rate
        seconds = 8  # Duration of recording
        
        print(f"\nListening... (Speak now for {seconds} seconds)")
        # Record audio
        myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()  # Wait until recording is finished
        print("Recognizing...")
        
        # Save as temporary WAV file
        wav.write('temp_voice.wav', fs, myrecording)
        
        recognizer = sr.Recognizer()
        with sr.AudioFile('temp_voice.wav') as source:
            audio = recognizer.record(source)
            
        try:
            text = recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text.lower()
        except sr.UnknownValueError:
            print("Sorry, I didn't catch that.")
            return ""
        except sr.RequestError as e:
            print(f"Could not request results from Speech Recognition service; {e}")
            return ""
            
    except ImportError:
        print("\n[WARNING] Microphone support libraries (sounddevice/scipy) are not installed.")
        print("Falling back to text input...")
        return input("\nType your command: ").lower()

SYSTEM_PROMPT = """
You are a smart PC AI Assistant. The user will speak to you.
If the user asks a general question, just reply normally with text.

If the user asks you to perform a PC task, YOU MUST reply ONLY with a JSON object, wrapped in ```json ``` markdown. 
The JSON must have an "action" key and relevant arguments.

Supported actions:
1. {"action": "create_word", "filename": "example.docx", "content": "text to write in file"}
2. {"action": "open_app", "app_name": "chrome"} (or notepad, whatsapp)
3. {"action": "send_whatsapp", "contact_name": "john", "message": "hello"}
4. {"action": "shutdown_pc"}

Example: If user says "Make a word file called notes and write hello world in it", 
you output EXACTLY:
```json
{
  "action": "create_word",
  "filename": "notes.docx",
  "content": "hello world"
}
```
"""

def generate_ai_response(prompt):
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=SYSTEM_PROMPT + "\n\nUser command: " + prompt,
        )
        return response.text
    except Exception as e:
        return f"I encountered an error connecting to my brain: {e}"

def execute_ai_action(action_data):
    action = action_data.get("action")
    
    if action == "create_word":
        filename = action_data.get("filename", "document.docx")
        if not filename.endswith(".docx"): 
            filename += ".docx"
        content = action_data.get("content", "")
        
        # Save to desktop
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        filepath = os.path.join(desktop_path, filename)
        
        try:
            doc = docx.Document()
            doc.add_paragraph(content)
            doc.save(filepath)
            speak(f"I have created the MS Word file {filename} on your desktop.")
        except Exception as e:
            speak(f"I failed to create the document. Error: {e}")
            
    elif action == "open_app":
        app_name = action_data.get("app_name", "").lower()
        if "chrome" in app_name:
            speak("Opening Google Chrome.")
            try:
                os.startfile("chrome.exe")
            except:
                pass
        elif "notepad" in app_name:
            speak("Opening Notepad.")
            subprocess.Popen("notepad.exe")
        elif "whatsapp" in app_name:
            speak("Opening WhatsApp.")
            try:
                # Try opening WhatsApp desktop app
                os.startfile("whatsapp:")
            except Exception:
                # Fallback to web
                speak("I couldn't find the Windows app, opening WhatsApp Web instead.")
                os.startfile("https://web.whatsapp.com")
        else:
            speak(f"I am not sure how to open {app_name} yet.")
            
    elif action == "send_whatsapp":
        contact_name = action_data.get("contact_name", "").lower()
        message = action_data.get("message", "")
        
        if contact_name in CONTACTS:
            phone_number = CONTACTS[contact_name]
            speak(f"Sending message to {contact_name}.")
            # pywhatkit opens web browser, types, and sends
            try:
                pywhatkit.sendwhatmsg_instantly(phone_number, message, 15, True, 2)
                speak("Message sent successfully.")
            except Exception as e:
                speak("I encountered an error while trying to send the message.")
        else:
            speak(f"I don't have {contact_name} in my address book. Please add their number to the CONTACTS dictionary in the code.")
            
    elif action == "shutdown_pc":
        speak("Shutting down the PC in 10 seconds. Save your work.")
        print("[SYSTEM ACTION]: shutdown /s /t 10")
        os.system("shutdown /s /t 10")
    else:
        speak(f"I don't know how to perform the action: {action}")

def parse_and_execute(ai_text):
    text = ai_text.strip()
    
    # Check if AI returned a JSON block
    if text.startswith("```json") and text.endswith("```"):
        # Extract json content
        json_str = text[7:-3].strip()
        try:
            action_data = json.loads(json_str)
            execute_ai_action(action_data)
            return True # It was an action
        except json.JSONDecodeError:
            speak("I understood the command but my brain's formatting was slightly off.")
            return True
            
    # Or if it returned raw JSON without markdown
    elif text.startswith("{") and text.endswith("}"):
        try:
            action_data = json.loads(text)
            execute_ai_action(action_data)
            return True
        except json.JSONDecodeError:
            pass
            
    return False # Not an action, just normal text

def main():
    speak("Hello! I am your AI agent. I can answer questions, create files, and open apps.")
    
    while True:
        command = listen()
        
        if not command:
            continue
            
        if "exit" in command or "stop" in command or "goodbye" in command:
            speak("Goodbye! Have a great day.")
            break
            
        # Local fast-path for common commands to bypass the API if you are rate-limited
        if "shut down" in command or "turn off pc" in command:
            execute_ai_action({"action": "shutdown_pc"})
            continue
        elif "chrome" in command and "open" in command:
            execute_ai_action({"action": "open_app", "app_name": "chrome"})
            continue
            
        # Ask AI to process the command
        ai_response = generate_ai_response(command)
        
        # Check if AI wanted to trigger a PC action
        is_action = parse_and_execute(ai_response)
        
        # If it wasn't an action, just speak the response
        if not is_action:
            speak(ai_response)

if __name__ == "__main__":
    main()
