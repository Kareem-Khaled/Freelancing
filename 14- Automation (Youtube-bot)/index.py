import os 
import sys
import random
import time
import urllib.request
from pexelsapi.pexels import Pexels
import moviepy.editor as mpe

musicDir = sys.path[0] + "\\music"
videoDir = sys.path[0] + "\\video"
outDir = sys.path[0] + "\\output"

def downloadVideo(link, num):
    try:
        name = str(int(time.time())) + '.mp4'
        urllib.request.urlretrieve(link, f'{videoDir}\\{name}')
        print(f"+ Video {num} download completed..!!")
        return name
    except Exception as e:
        print(e)
    
def combine_audio(vidname, audname, outname, fps=25):
    try:
        my_clip = mpe.VideoFileClip(vidname)
        audio_background = mpe.AudioFileClip(audname).subclip(0, my_clip.duration)
        final_clip = my_clip.set_audio(audio_background)
        final_clip.write_videofile(outname, fps)
    except Exception as e:
        print(e)

def getMusic():
    musics = os.listdir(musicDir)
    return f'{musicDir}\\{musics[random.randint(0, len(musics) - 1)]}'

downloadSet = set()
def updataData(op):
    with open('downloaded.txt', f'{op}') as f:
        if op == 'r':
            for line in f:
                downloadSet.add(line.strip())
        else:
            for i in downloadSet:
                f.write(i + '\n')
vidNames = []
def get_final_videos():
    cnt = 1
    for vid in vidNames:
        combine_audio(f'{videoDir}\\{vid}', getMusic(), f'{outDir}\\{vid}')
        print(f"+ video {cnt} Merging completed..!!")
        cnt += 1

def PexelsApi():
    targetVid = max(1, int(input('Please enter the number of videos you want to download: ')))
    tag = 'moon' or input('Please enter the videos tag: ')

    PEXELS_API = '563492ad6f917000010000013ae2a1d20ee54fb5865ba2d817521a38'
    pexel = Pexels(PEXELS_API)
    downloadedVid = 1
    curPage = 1
    while downloadedVid < targetVid:
        videos = pexel.search_videos(query=tag, orientation='portrait', page=curPage, per_page=min(targetVid*2, 80))
        if not len(videos['videos']): break
        for vid in videos['videos']:
            try:
                link = vid['video_files'][0]['link']
                if link in downloadSet: continue
                downloadSet.add(link)
                vidNames.append(downloadVideo(link, str(downloadedVid)))
                if downloadedVid == targetVid: 
                    break
                downloadedVid += 1
            except: pass
        curPage += 1
            
    print(f'{downloadedVid}/{targetVid} downloaded succefully!')

if __name__ == '__main__':
    updataData('r')
    PexelsApi()
    updataData('w')
    get_final_videos()