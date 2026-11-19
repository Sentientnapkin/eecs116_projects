GPU flight kit (EECS 116 viobench): makes varied, hidden-set-like test flights on a GPU computer. Testing stays on the laptop.

1. Copy this gpu_kit folder to the GPU computer (Linux; native Linux with the NVIDIA driver works best).
2. bash setup.sh ~/path/to/your/viobench/clone    (no path = fresh clone into ~/viobench)
     Installs viobench + our autopilot patch, renders a 10 s test flight. It must say "OK: GPU renderer in use".
3. bash calibrate.sh      Quick 30 s check of the 3 speed styles: shows each flight's speed range, flags crashes.
4. bash make_flights.sh   About 86 one-minute flights (each with its own top speed, 0.3-4 m/s) into ~/flights_gpu/<group>/ (re-run to resume if interrupted).
5. Bring the flights back to the laptop. NOT through git (each flight is 100-600 MB; GitHub refuses files over 100 MB).
   From the laptop:  scp -r USER@MACHINE.eecs.berkeley.edu:~/flights_gpu C:/Users/alexa/Downloads/   (or a USB drive)
   then tell Claude where they are.

No team token or solution code is needed on the GPU computer.
