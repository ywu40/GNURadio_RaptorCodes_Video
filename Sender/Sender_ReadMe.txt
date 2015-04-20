Part One: Compile C++ Raptor codes
1. Compile the C++ codes of Raptor codes in C++ fold
sudo swig -c++ -python raptor_encoder.i
sudo python setup_encoder.py build_ext --inplace

2. After step 1, copy the following files to the directory gnuradio/gr-digital/examples/narrowband
_raptor_encoder.so
raptor_encoder.py

-----------------------------------------------------------------------------------------------------------

Part Two: Transmission
3. Use the below command to start the sender
1) With Raptor codes case:
python wyq_raptor_video_tx.py --tx-freq=908M --rx-freq=921975000 --rx-gain=30 --tx-gain=30 --tx-amplitude=1 --PLR=1 -T 200

2) Raw video data case:
sudo python wyq_raw_video_tx.py --tx-freq=908M --rx-freq=921975000 --rx-gain=30 --tx-gain=30 --tx-amplitude=1 -T 200

Options: 
PLR: packet loss rate
T: packet length

Note: Please start the receiver first, then startup the sender.

