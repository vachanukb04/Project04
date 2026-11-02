"""Optional native macOS Speech helper. No always-on recording and no saved audio."""
import json
import platform
import plistlib
from pathlib import Path
import shutil
import subprocess
import time
from .bridge import ROOT

def build_voice(build):
    if platform.system()!='Darwin':raise RuntimeError('Voice feedback requires macOS. C/Y/N typed feedback remains available.')
    if shutil.which('xcrun') is None:raise RuntimeError('Install Apple command-line tools: xcode-select --install. Typed feedback works without them.')
    arch='arm64' if platform.machine() in ('arm64','aarch64') else 'x86_64'
    deployment='11.0' if arch=='arm64' else '10.15'
    bundle=Path(build).resolve()/'Project04Feedback.app'
    contents=bundle/'Contents';binary=contents/'MacOS/FeedbackSpeech'
    binary.parent.mkdir(parents=True,exist_ok=True)
    info={'CFBundleExecutable':'FeedbackSpeech','CFBundleIdentifier':'com.project04.feedback',
          'CFBundleName':'Project04 Feedback','CFBundlePackageType':'APPL',
          'CFBundleVersion':'1','LSUIElement':True,'LSMinimumSystemVersion':deployment,
          'NSMicrophoneUsageDescription':'Listen to your requested object-name correction.',
          'NSSpeechRecognitionUsageDescription':'Transcribe object-name feedback after you request listening.'}
    (contents/'Info.plist').write_bytes(plistlib.dumps(info))
    source=ROOT/'app/macos/FeedbackSpeech.swift'
    if not binary.exists() or source.stat().st_mtime>binary.stat().st_mtime:
        run=subprocess.run(['xcrun','swiftc','-swift-version','5','-target',f'{arch}-apple-macosx{deployment}',str(source),'-o',str(binary),
            '-framework','AppKit','-framework','AVFoundation','-framework','Speech'],capture_output=True,text=True,timeout=120)
        if run.returncode:raise RuntimeError('Speech helper did not compile:\n'+run.stdout+run.stderr)
        run=subprocess.run(['codesign','--force','--deep','--sign','-',str(bundle)],capture_output=True,text=True,timeout=30)
        if run.returncode:raise RuntimeError('Could not sign local speech helper:\n'+run.stdout+run.stderr)
    return binary

def listen_once(binary,allow_network=False,cancel=None):
    command=[str(binary)]+(['--allow-network'] if allow_network else [])
    deadline=time.monotonic()+75
    with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as process:
        while True:
            try:
                output,error=process.communicate(timeout=.2)
                break
            except subprocess.TimeoutExpired:
                if (cancel is not None and cancel.is_set()) or time.monotonic()>deadline:
                    process.kill();process.communicate()
                    raise RuntimeError('Voice canceled or timed out. Typed feedback remains available.')
        code=process.returncode
    try:payload=json.loads(output.strip().splitlines()[-1])
    except (ValueError,IndexError):raise RuntimeError('Voice helper failed: '+error.strip())
    if code or 'error' in payload:raise RuntimeError(payload.get('error',error))
    return payload['transcript']
