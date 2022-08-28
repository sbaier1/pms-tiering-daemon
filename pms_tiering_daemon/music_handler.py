import parsedatetime as pdt
import time
import logging
import datetime
from os.path import exists, isfile
from os import remove
from shutil import copyfile
from threading import Timer


class MusicHandler:
    def __init__(self, config, library, init_time_metric, objects_handled, objects_moved_cold, objects_moved_hot,
                 bitrate_threshold_exceeded, incremental_time_metric):
        self.refresh_interval = None
        self.play_count_window_start = None
        self.config = config
        self.library = library
        self.init_time_metric = init_time_metric
        self.objects_handled = objects_handled
        self.objects_moved_cold = objects_moved_cold
        self.objects_moved_hot = objects_moved_hot
        self.bitrate_threshold_exceeded = bitrate_threshold_exceeded
        self.incremental_time_metric = incremental_time_metric
        self.cal = pdt.Calendar()

    def initialize(self):
        self.refresh_timeframe()
        if self.config["initialFullScan"]:
            logging.info(f"Starting a full scan for library {self.library.title}")
            start_millis = int(round(time.time() * 1000))
            with self.init_time_metric.time():
                tracks = self.library.searchTracks()
                for track in tracks:
                    self.handle_track(track)
                    self.objects_handled.inc()
            duration = int(round(time.time() * 1000)) - start_millis
            logging.info(f"Finished full scan for library {self.library.title} in {duration}ms")
        self.cal.parse(self.config["refreshInterval"])
        self.refresh_interval = (self.cal.parseDT(self.config["refreshInterval"],
                                                  sourceTime=datetime.datetime.min)[0] - datetime.datetime.min).seconds
        Timer(self.refresh_interval, self.refresh_tracks).start()

    def refresh_tracks(self):
        self.refresh_timeframe()
        # TODO: run the search filtering for the playback timeframe. pass the tracks to handle tracks.
        Timer(self.refresh_interval, self.refresh_tracks).start()

    def handle_track(self, track):
        bitrate_threshold = self.config["bitrateThreshold"]
        if len(track.media) > 0:
            # We only care about the first media object for now
            medium = track.media[0]
            if bitrate_threshold > 0:
                bitrate = medium.bitrate
                if bitrate > bitrate_threshold:
                    self.bitrate_threshold_exceeded.inc()
                    return

            if len(medium.parts) > 0:
                part = medium.parts[0]
                original_location = part.file
                cold_tier_location = part.file.replace(self.config["mergerLocation"], self.config["coldTierLocation"])
                hot_tier_location = part.file.replace(self.config["mergerLocation"], self.config["hotTierLocation"])

                # TODO also consider play history count for minPlayCount
                # TODO we can probably skip this check if we run from an incremental scan
                if not track.lastViewedAt or track.lastViewedAt <= self.play_count_window_start:
                    # Object moves to cold tier
                    # ensure the file exists in cold tier
                    if exists(cold_tier_location) and isfile(cold_tier_location):
                        remove(hot_tier_location)
                        logging.debug(f'Moved object {original_location} to cold storage')
                        self.objects_moved_cold.inc()
                    else:
                        logging.warning(f'Object at {original_location} did not exist in cold storage, moving it '
                                        f'there to bring filesystem in sync first')
                        if exists(hot_tier_location) and isfile(hot_tier_location):
                            copyfile(hot_tier_location, cold_tier_location)
                            remove(hot_tier_location)
                        else:
                            logging.warning(f'Object at {original_location} exists neither in hot nor in cold storage')
                            return
                else:
                    # Object stays or moves to hot tier
                    # ensure the file exists in cold tier
                    if exists(hot_tier_location) and isfile(hot_tier_location):
                        logging.debug(f'Object at {original_location} already exists in hot storage')
                    else:
                        logging.warning(f'Object at {original_location} did not exist in hot storage, copying it '
                                        f'there to bring filesystem in sync first')
                        if exists(cold_tier_location) and isfile(cold_tier_location):
                            copyfile(cold_tier_location, hot_tier_location)
                            logging.debug(f'Moved object {original_location} to hot storage')
                            self.objects_moved_hot.inc()
                        else:
                            logging.warning(f'Object at {original_location} exists neither in hot nor in cold storage')

    def refresh_timeframe(self):
        time_struct, parse_status = self.cal.parse(f'-{self.config["playCountWindow"]}')
        self.play_count_window_start = datetime.datetime(*time_struct[:6])
