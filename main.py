"""
Xavier Thee Second: YouTube Viral Video Clipper & Auto-Poster

This script downloads YouTube videos, detects viral clips, edits them, and uploads to your channel.
"""
import os
import numpy as np
from googleapiclient.discovery import build
from oauth2client.tools import run_flow
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets
import yt_dlp
import moviepy.editor as mp

# CONFIGURATION
VIDEO_URLS = [
    # Add YouTube video URLs here as strings, e.g. "https://www.youtube.com/watch?v=XXXX"
]
CLIP_DURATION = 60  # seconds
OUTPUT_DIR = "clips"

# AUTHENTICATION - YouTube Data API
# (Requires credentials.json in the project root)

def authenticate_youtube():
    flow = flow_from_clientsecrets('credentials.json',
                                   scope='https://www.googleapis.com/auth/youtube.upload')
    storage = Storage('oauth2.json')
    creds = storage.get()
    if not creds or creds.invalid:
        creds = run_flow(flow, storage)
    return build('youtube', 'v3', credentials=creds)

def download_video(url, output_path):
    ydl_opts = {
        'format': 'best[ext=mp4]',
        'outtmpl': output_path,
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def find_viral_clips(video_path, clip_duration=60, top_n=3):
    video = mp.VideoFileClip(video_path)
    audio = video.audio
    step = 0.5
    n_steps = int(video.duration // step)
    rms = []
    for i in range(n_steps):
        t0 = i * step
        t1 = min(t0 + step, video.duration)
        arr = audio.subclip(t0, t1).to_soundarray(fps=22050)
        rms.append(np.sqrt(np.mean(arr**2)))
    rms = np.array(rms)

    window = int(clip_duration // step)
    if window == 0:
        window = 1
    loudness = np.convolve(rms, np.ones(window)/window, mode='valid')
    # Find the top N loudest windows, avoid overlapping
    best_idxs = []
    loudness_copy = loudness.copy()
    for _ in range(min(top_n, len(loudness_copy))):
        idx = np.argmax(loudness_copy)
        best_idxs.append(idx)
        # Zero out neighbors to prevent overlap
        left = max(0, idx - window)
        right = min(len(loudness_copy), idx + window)
        loudness_copy[left:right] = -np.inf
    starts = sorted([i * step for i in best_idxs])
    return [(start, min(start + clip_duration, video.duration)) for start in starts]

def create_clip(video_path, start, end, output_path):
    video = mp.VideoFileClip(video_path).subclip(start, end)
    video.write_videofile(output_path, codec="libx264")

def upload_clip(youtube, clip_path, title, description):
    body = dict(
        snippet=dict(
            title=title,
            description=description,
            tags=["viral", "clip"]
        ),
        status=dict(
            privacyStatus="public"
        )
    )
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=clip_path
    )
    response = request.execute()
    return response

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    youtube = authenticate_youtube()
    for url in VIDEO_URLS:
        print(f"Processing {url}")
        video_fname = os.path.join(OUTPUT_DIR, "downloaded.mp4")
        download_video(url, video_fname)
        for idx, (start, end) in enumerate(find_viral_clips(video_fname, CLIP_DURATION)):
            clip_path = os.path.join(OUTPUT_DIR, f"clip_{idx+1}.mp4")
            create_clip(video_fname, start, end, clip_path)
            upload_clip(youtube, clip_path, f"Viral Clip #{idx+1}", f"Auto-created viral moment from {url}")
            print(f"Uploaded {clip_path}")

if __name__ == "__main__":
    main()
