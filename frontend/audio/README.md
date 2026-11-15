# SOS / drill siren

`sos-alarm.mp3` is an excerpt of the user-supplied file
`Yangın Alarmı Siren Sesi.mp4` (source duration 58.607 seconds).
This is the uploaded recording, not a synthesized imitation or a YouTube embed.

- Source interval: 00:04–00:16 (12 seconds).
- Mono, 44.1 kHz, 96 kbps MP3; approximately 145 kB.
- Gain reduced by 3 dB before encoding; 15 ms fades at both ends.
- The Web Audio player loops the decoded buffer for the selected alarm duration
  (15/30/60 seconds), with a quieter two-second preview.
- Included in the Service Worker shell for offline reuse after installation.
- If fetching or decoding fails, the existing paired-tone fallback remains
  available; the next enable-sound click retries the file.

Reproduce from the original upload:

```sh
ffmpeg -ss 4 -i 'Yangın Alarmı Siren Sesi.mp4' -t 12 -vn -ac 1 -ar 44100 \
  -af 'volume=-3dB,afade=t=in:st=0:d=0.015,afade=t=out:st=11.985:d=0.015' \
  -c:a libmp3lame -b:a 96k -map_metadata -1 sos-alarm.mp3
```
