# 📺 Upcoming TV Shows for Kometa

**UTSK** (Upcoming TV Shows for Kometa) creates a 'coming soon' collection in your Plex server. It accomplishes this by
-  checking [Sonarr](https://sonarr.tv/) for upcoming (monitored) shows within x days.
-  downloading a trailer using [yt-dlp](https://github.com/yt-dlp/yt-dlp) and saving it as a special (S00E00) so the show gets picked up by Plex.
-  creating collection and overlay .yml files which can be used with [Kometa](https://kometa.wiki/en/latest/) (formerly Plex Meta Manager).

<sub>Can be used alongside [TV Show Status for Kometa](https://github.com/netplexflix/TV-show-status-for-Kometa)</sub>

## Example:
<img width="1303" height="495" alt="Image" src="https://github.com/user-attachments/assets/bd2718b0-2437-44f7-8da6-2b819dece7b7" />

---
## 🛠️ Installation


### 1️⃣ Clone the repository:
   ```bash
   git clone https://github.com/netplexflix/Upcoming-TV-Shows-for-Kometa.git
   cd Upcoming-TV-Shows-for-Kometa
   ```
> [!TIP]
>If you don't know what that means, then simply download the script by pressing the green 'Code' button above and then 'Download Zip'.  
>Extract the files to your desired folder.


### 2️⃣ Install Python dependencies:
- Ensure you have [Python](https://www.python.org/downloads/) installed (`>=3.11`).
- Open a Terminal in the script's directory
> [!TIP]
>Windows Users:  
>Go to the UTSK folder (where UTSK.py is). Right mouse click on an empty space in the folder and click `Open in Windows Terminal`.
- Install the required dependencies by running:
```sh
pip install -r requirements.txt
```

### 3️⃣ Install ffmpeg
[ffmpeg ](https://www.ffmpeg.org/) is required by yt-dlp to do postprocessing.
Check [THIS WIKI](https://www.reddit.com/r/youtubedl/wiki/ffmpeg/#wiki_where_do_i_get_ffmpeg.3F) for more information on how to install ffmpeg.

---

## ⚙️ Configuration

Rename `config.example.yml` to `config.yml` and update your settings:


#### <ins>Sonarr Configuration:</ins>
- **sonarr_url:** Change if needed
- **sonarr_api_key:** Can be found in Sonarr under settings => General => Security.
- **skip_unmonitored:** Recommended keeping this set to `true` since only monitored shows will actually be downloaded.
  
#### <ins>General:</ins>
- **utc_offset:** Set the [UTC timezone](https://en.wikipedia.org/wiki/List_of_UTC_offsets) offset. e.g.: LA: -8, New York: -5, Amsterdam: +1, Tokyo: +9, etc
>[!NOTE]
> Some people may run their server on a different timezone (e.g. on a seedbox), therefor the script doesn't convert the air dates to your machine's local timezone. Instead, you can enter the utc offset you desire.
- **future_days_upcoming_shows:** within how many days the premiere has to air
- **debug:** set to `true` to troubleshoot yt-dlp problems
- **skip_channels:** Blacklist Youtube channels that create fake trailers
- **download_trailers:** You could set to `false` to skip downloading (dry run)

#### <ins>path mapping</ins>
Add path mapping if needed, for example if you're using unRAID.

#### <ins>.yml settings:</ins>
The other settings allow you to customize the output of the collection and overlay .yml files.
>[!NOTE]
> These are date formats you can use:<br/>
> `d`: 1 digit day (1)<br/>
> `dd`: 2 digit day (01)<br/>
> `ddd`: Abbreviated weekday (Mon)<br/>
> `dddd`: Full weekday (Monday)<br/>
><br/>
> `m`: 1 digit month (1)<br/>
> `mm`: 2 digit month (01)<br/>
> `mmm`: Abbreviated month (Jan)<br/>
> `mmmm`: Full month (January)<br/>
><br/>
> `yy`: Two digit year (25)<br/>
> `yyyy`: Full year (2025)
>
>Dividers can be `/`, `-` or a space

## ☄️ Add the collection and overlay files to your Kometa config

Open your **Kometa** config.yml (typically at `Kometa/config/config.yml`) and add the path to the UTSK .yml files under `collection_files` and `overlay_files`

Example:
```yaml
TV Shows:
  collection_files:
    - file: P:/scripts/UTSK/Kometa/UTSK_TV_UPCOMING_SHOWS_COLLECTION.yml
  overlay_files:
    - file: P:/scripts/UTSK/Kometa/UTSK_TV_UPCOMING_SHOWS_OVERLAYS.yml

```

---

## 🚀 Usage - Running the Script

Open a Terminal in your script directory and launch the script with:
   ```bash
   python UTSK.py
   ```

---

## 💡TIP: Prevent these shows from showing up under "Recently Added TV"
This script will add shows to Plex with only a trailer since they aren't actually out yet. You probably want to avoid seeing them pop up in your "Recently Added TV" section on your home screen because you and/or your users will think it's actually available already.
To accomplish this I strongly recommend replacing the default "Recently Added TV" collection with your own smart collection:

1. Go to your TV show library
2. Sort by "Last Episode Date Added" (make sure it says 'TV Shows' to the left of it and not 'Episodes')
3. Press the '+' burger menu icon on the right then click "create smart collection"
4. Add filter `Label` `is not` `Coming Soon` (or whatever you used as collection_name. Since the collection yml uses smart_label, Kometa adds that label to the relevant shows, so you can exclude these shows based on that label. The label will be automatically removed by Kometa once the show is no longer 'upcoming' so when the first episode is added, it will show up)
5. Press 'Save As' > 'Save As Smart Collection'
6. Name it something like "New in TV Shows📺"
7. In the new collection click the three dots then "Visible on" > "Home"
8. Go to Settings > under 'manage' click 'Libraries' > Click on "Manage Recommendations" next to your TV library
9. Unpin the default "Recently Added TV" and "Recently Released Episodes" from home, and move your newly made smart collection to the top (or wherever you want it)

You have now replaced the default home categories with your own, more flexible one that will simply bump the show forward when a new episode is added, while it excludes these 'dummy' shows that are not actually out yet.
You can do loads of other things with it this way. For example exclude certain shows from showing up by using genre (e.g. talk shows) or your own custom label you can manually apply to certain individual shows you don't want to show up in this home banner.

<img width="809" height="161" alt="Image" src="https://github.com/user-attachments/assets/0cf0924e-1bcd-4871-87cf-7a3e5420aa0c" />

</br></br>

## 💡TIP2: Combine UTSK with the "New Season Soon" collection of [TSSK](https://github.com/netplexflix/TV-show-status-for-Kometa)
![Image](https://github.com/user-attachments/assets/2843ae7f-3bf9-4b6c-b1da-bb0a513d0de0)

You can use the following collection code to have Kometa apply a label to the shows without actually making the collection:

```yml
collection_upcoming_shows:
  collection_name: "Coming Soon UTSK"
  item_label: Coming Soon
  non_item_remove_label: Coming Soon
  build_collection: false
```

You can do the same for the "New Season Soon" collection of [TSSK](https://github.com/netplexflix/TV-show-status-for-Kometa), then manually create a smart collection that combines both upcoming new seasons as well as new premieres:

<img width="795" height="257" alt="Image" src="https://github.com/user-attachments/assets/398574a6-0046-4f28-bbc0-671c5c5c0646" />


---

### ⚠️ **Do you Need Help or have Feedback?**
- Join the [Discord](https://discord.gg/VBNUJd7tx3).

  
---  
### ❤️ Support the Project
If you like this project, please ⭐ star the repository and share it with the community!

<br/>

[!["Buy Me A Coffee"](https://github.com/user-attachments/assets/5c30b977-2d31-4266-830e-b8c993996ce7)](https://www.buymeacoffee.com/neekokeen)
