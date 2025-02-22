# My 48VDC system
This repository gives an overview of my 48VDC system and serves as a collection point for interesting information about the components of my system.

## System overview
![48VDC_System_overview.jpg](./pictures/48VDC_System_overview.jpg)
The mainly important components of this system are:
  - VICTRON MultiPlus-II 48-3000-35 inverter
  - DEYE RW-M6.1 Battery
  - MEANWELL RSP-500-48 power supply (sligthly modified and enhanced)

I use these components to create a telecommunication like 48VDC system at my home. Due to a relatively new building, i installed 2014 a couple of additionaly cables between my power distribution units in each floor and can thereby good distribute the power to the required loads.
These loads are my automation units (for example KNX and DALI devices), network switches, router, PoE devices, but also my whole LED lighting in ground floor.
Initially 4 old lead-acid car batteries were the "core" of my system and my modified 500 Watt MEANWELL power supply was my intelligent charger for this system.
![48VDC_Power_supply.jpg](./pictures/48VDC_Power_supply.jpg)
I monitored this system using GRAFANA and observed the balancing between the 4 batteries.
Due to slightly load (I did not connected lighting initially) and very powerful China balancers I could compensate one of 4 batteries completely and thus I have time to find the next old battery for my system.
But lead-acid batteries and mainly old car batteries do not have enough residal capacity. Finaly I changed almost every month at least one battery from this lead-acid system and the whole work was very laborious.   
Since October 2023 I replaced my old lead-acid system by I nice DEYE RW-M6.1 battery. Usualy a DEYE battery is operated together with a DEYE inverter. But poor documentation for DEYE products and incompetence of their distributor from Berlin have an impact on my decision for VICTRON inverter.
![VICTRON_Multiplus_II.jpg](./pictures/VICTRON_Multiplus_II.jpg)
VICTRON inverters are very good documented and are known from maritime area. Also the using of a Linux based "Venus OS" and posibility to use of a "Raspberry Pi" as control unit for the inverter are essential "pro" factors for this product.
The MultiPlus-II inverter can rudimentary monitor, charge and discharge the RW-M6.1 battery, but this battery will not detected correctly from the native CAN driver of "Venus OS". For this reason, since December 2024 I started looking for a alternative and practicable solution and found a Python project ["venus-os_dbus-serialbattery"](https://github.com/mr-manuel/venus-os_dbus-serialbattery/tree/master) that allows support for additionaly batteries, which are not supported natively by "Venus OS".
["venus-os_dbus-serialbattery"](https://github.com/mr-manuel/venus-os_dbus-serialbattery/tree/master) was initially created to support the batteries over serial communication (UART, RS485), but last years this project was enhanced by support for CAN communication. Also two different BMS/Battery types are actually implemented as Python scripts and can serve as a good template for similar projects.
I am not a professional programmer and Python is really the badest programming language, which I know, but I did not a really alternative, as to write my own Python based "driver" for DEYE battery under "Venus OS".
