Part One: Compile C++ Raptor codes
1. Compile the C++ codes of Raptor codes in C++ fold
sudo swig -c++ -python raptor_decoder.i
sudo python setup_decoder.py build_ext --inplace

2. After step 1, copy the following files to the directory gnuradio/gr-digital/examples/narrowband
_raptor_decoder.so
raptor_decoder.py

-----------------------------------------------------------------------------------------------------------

Part Two: Transmission
3. Use the below command to start the receiver
1) With Raptor codes case:
python wyq_raptor_video_rx.py --rx-freq=908M --tx-freq=921975000 --rx-gain=30 --tx-gain=30 --tx-amplitude=1 --PLR=1

2) Raw video data case:
python wyq_raw_video_rx.py --rx-freq=908M --tx-freq=921975000 --rx-gain=30 --tx-gain=30 --tx-amplitude=1 --PLR=1

Note: Please start the receiver first, then startup the sender.

-------------------------------------------------------------------------------------------------------------

Part Three: Experiments with parts of frames
After finishing the receiving, using the below command to play the video
1. Raptor codes case: the Sequence with parts of frames
1) The received h264 stream---output_raptor.264
2) convert it into yuv (raw video) format
avconv -i output_raptor.264 -s 352x288 output_raptor.yuv

Note:
a)output_raptor.yuv is the yuv (raw video) format
b)avconv is a tool of ffmpeg
c)-i: input file
d)-s: the video resolution (or size), in this experiment is cif (352*288)

3) Using mplayer to play the yuv format video
mplayer output_raptor.yuv -demuxer rawvideo -rawvideo cif

2. Raw video case: the Sequence with parts of frames
1) The received h264 stream---output_no_raptor.264
2) convert it into yuv (raw video) format
avconv -i output_no_raptor.264 -s 352x288 output_no_raptor.yuv

Note:
a)output_no_raptor.yuv is the yuv (raw video) format
b)avconv is a tool of ffmpeg
c)-i: input file
d)-s: the video resolution (or size), in this experiment is cif (352*288)

3) Using mplayer to play the yuv format video
mplayer output_no_raptor.yuv -demuxer rawvideo -rawvideo cif

Since Professor Kumar required to replay the three video data (original video data, with Raptor codes, raw video data) simultaneously,
you can input the following three command at different terminal, then start them simultaneous:
mplayer output_raptor.yuv -demuxer rawvideo -rawvideo cif
mplayer output_no_raptor.yuv -demuxer rawvideo -rawvideo cif
mplayer foreman_cif.yuv -demuxer rawvideo -rawvideo cif

---------------------------------------------------------------------------------------------------------

Part Four: Experiments with the whole frames (as you required, I put the preprocessing whole sequence in the fold Ke Bao)
1. Raptor codes case: the Sequence with the whole frames
1) The received h264 stream---output_raptor_full.264
2) convert it into yuv (raw video) format
avconv -i output_raptor_full.264 -s 352x288 output_raptor_full.yuv

Note:
a)output_raptor_full.yuv is the yuv (raw video) format
b)avconv is a tool of ffmpeg
c)-i: input file
d)-s: the video resolution (or size), in this experiment is cif (352*288)

3) Using mplayer to play the yuv format video
mplayer output_raptor_full.yuv -demuxer rawvideo -rawvideo cif

2. Raw video case: the Sequence with the whole frames
1) The received h264 stream---output_no_raptor_full.264
2) convert it into yuv (raw video) format
avconv -i output_no_raptor_full.264 -s 352x288 output_no_raptor_full.yuv

Note:
a)output_no_raptor_full.yuv is the yuv (raw video) format
b)avconv is a tool of ffmpeg
c)-i: input file
d)-s: the video resolution (or size), in this experiment is cif (352*288)

3) Using mplayer to play the yuv format video
mplayer output_no_raptor_full.yuv -demuxer rawvideo -rawvideo cif

