# MiBand-HRX
Library to work with Xiaomi MiBand HRX Edition Accelerometer Data. Intended for extraction of accelerometer data only,
for experimentaions with ROS and gesture recognition.

I couldn't find a solution that worked with MiBand HRX edition. This repo is forked from [creotiv/MiBand2](https://github.com/creotiv/MiBand2) and modified to work with HRX bands.

The following commands were helpful in identification of services and characteristics specific to HRX bands. Xiaomi doesn't provide user descriptions for the services and characteristics, which makes it harder. There are plenty of reverse engineered solutions for MiBand2 & 3 which were extremely [helpful](#sources--references).

#### List services

```sh
gatttool -b <MAC-ADDRESS> -t random --primary
```

#### List characteristics

```sh
gatttool -b <MAC-ADDRESS> -t random --characteristics
```


# BLE
- Authentication is same as MiBand2
- Services & Characteristics of interest

    - ``SERVICE_MIBAND1 : "0000fee1-0000-1000-8000-00805f9b34fb"``
        - ``CHARACTERISTIC_SENSOR_CONTROL : "00000001-0000-3512-2118-0009af100700"``
        - ``CHARACTERISTIC_SENSOR_MEASURE : "00000002-0000-3512-2118-0009af100700"``

- To receive accelerometer notification
    - Write without response ``0x010119`` to service ``0000fee1-0000-1000-8000-00805f9b34fb`` characeteristic ``00000001-0000-3512-2118-0009af100700``
    - Write without response ``0x02`` to service ``0000fee1-0000-1000-8000-00805f9b34fb`` characeteristic ``00000001-0000-3512-2118-0009af100700``
    - Write ``0x0100`` to notification descriptor to enable notification

# Processing Accelerometer Data

## Parsing
Data received in packets of byte size ``20``, ``14`` or ``8``.

Sample: ``0x0100 0500 8200 0b00 0400 8000 0b00 0300 8100 0b00``


|0100  | 0500  | 8200  | 0b00 | 0400  | 8000  | 0b00  | 0300  | 8100  | 0b00   |
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| -  | signed x  |signed y   | signed z  |  signed x |  signed y | signed z  | signed x  | signed y  |  signed z |

## Calculating Roll and Pitch
In the absence of linear acceleration, the accelerometer output is a measurement of the rotated
gravitational field vector and can be used to determine the accelerometer pitch and roll orientation
angles.

<img src="roll_pitch_eqn.png" width="400">

## Plot
<img src="accel_plot.gif" width="1200">




# Sources & References
1) [Base lib provided by Leo Soares](https://github.com/leojrfs/miband2)
2) [Volodymyr Shymanskyy](https://github.com/vshymanskyy/miband2-python-test)
3) [Freeyourgadget Team](https://github.com/Freeyourgadget/Gadgetbridge/tree/master/app/src/main/java/nodomain/freeyourgadget/gadgetbridge/service/devices/huami/miband2)
4) [ragcsalo's Comment](https://github.com/Freeyourgadget/Gadgetbridge/issues/63#issuecomment-493740447)
5) [Xiaomi band protocol analyze](http://changy-.github.io/articles/xiao-mi-band-protocol-analyze.html)
6) [Tilt Sensing Using 3-Axis Accelerometer](https://www.nxp.com/docs/en/application-note/AN3461.pdf)
7) [creotiv donate link](https://github.com/creotiv/MiBand2#donate)



# Run 

1) Install dependencies
```sh
pip install -r requirements.txt
```
2) Turn on your Bluetooth
3) Unpair you MiBand from current mobile apps
4) Find out you MiBand MAC address
```sh
sudo hcitool lescan
```
5) Run this to auth device
```sh
python example.py --mac MAC_ADDRESS --init
```
6) Run this to call demo functions
```sh
python example.py --standard --mac MAC_ADDRESS
python example.py --help
```
7) If you having problems(BLE can glitch sometimes) try this and repeat from 4)
```sh
sudo hciconfig hci0 reset
```
