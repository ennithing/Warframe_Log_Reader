Warframe Combat Log

A project i started after my wife told me about ee.log, asking if that's interesting to me. Yup it was.

This is my take at a warframe combat log.
It parses EE.log from %localappdata%\Warframe\EE.log into a less cluttered, more readable, easy access format.
It allows you to parse the currently existing log (assuming you played warframe on this machine before) and then
switches into observation mode to further detect any incoming log line.

This kind of makes it a realtime combat log, which is why i decided to rename it into that.
It's super convenient to have running on a second monitor or to check a recent death in hindsight.

It is intended for those who are not satisfied with semlar. (https://semlar.com/deathlog)
To be brutally honest, semlar does the same thing with a little less glitter and a little less information here and there.
It does not require a download and is suitable for you if you don't want to observe the log continuously.
Unfortunately, my intention of this program was not one that was realizable using a web app. At least not for me.

This Script/App does the following:
  - When a Player, a Pet, a Companion, a Defection Target etc. gets 'Killed'
  - When a Player, a Pet, a Companion, a Defection Target etc. gets 'Downed'
  - Timestamps of all Events
  - Extracts the following information from the log:
    - Killed Subject
    - Enemy causing the Killshot
    - Level of the Enemy, if given
    - Damage source, if given
    - Damage inflicted to shield/hp
  - When the log spits out Damage warnings
  - When the log spits out negative value warnings
  - When a nemesis gets spawned
  - When a nemesis gets killed (and calculates the timedelta for your personal challenge)

  What it doesn't do:
    - It does not save your logs. At its current state it is not designed to save the parsed logs on your machine.
    - It does not take any of your data. Yeah, there is personal data in your log, such as region and timezone, but
      aside from your timezone and starting time of your last warframe instance, none of those information get used at all.
      The program doesn't recognize them as useful information.
    - It does not calculate your DPS, as Damage does not get logged in a reliable way.
    - It does not display revives.
    - It does not send any information anywhere.

The whole thing is coded in python, using PyInstaller, specifically auto-py-to-exe for it's convenience, to form an exe.

Hope you guys enjoy.
  
