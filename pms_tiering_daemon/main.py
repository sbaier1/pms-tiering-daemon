import os
import sys

from plexapi.library import MusicSection
from prometheus_client import start_http_server, Summary, Counter
import yaml
import logging
from plexapi.myplex import MyPlexAccount
from multiprocessing.pool import ThreadPool

from pms_tiering_daemon.music_handler import MusicHandler

METRIC_PREFIX = 'pms_tiering_'


def main():
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    logging.info("Loading configuration...")
    with open("/tmp/config.yaml", "r") as yamlfile:
        config = yaml.load(yamlfile, Loader=yaml.FullLoader)
        # Run some sanity checks
        if config["mergerLocation"] == config["hotTierLocation"]:
            logging.error("mergerLocation must not be equal to hotTierLocation")
            sys.exit(1)
        if config["mergerLocation"] == config["coldTierLocation"]:
            logging.error("mergerLocation must not be equal to coldTierLocation")
            sys.exit(1)
        if config["hotTierLocation"] == config["coldTierLocation"]:
            logging.error("hotTierLocation must not be equal to coldTierLocation")
            sys.exit(1)

        logging.info(f"Loaded config {config}")
        if config["enableMetrics"]:
            logging.info("Enabling prometheus metrics")
            start_http_server(9090)
        logging.info("Connecting to plex")
        account = MyPlexAccount(config["username"], config["password"])
        plex = account.resource(config["server"]).connect()
        libraries = config["libraries"]
        thread_pool = ThreadPool(len(libraries))
        init_time_metric = Summary(f'{METRIC_PREFIX}library_initial_scan', 'Time spent scanning the library initially',
                                   ['type', 'name'])
        incremental_time_metric = Summary(f'{METRIC_PREFIX}library_incremental_scan',
                                          'Time spent scanning the library incrementally',
                                          ['type', 'name'])
        objects_handled = Counter(f'{METRIC_PREFIX}objects_handled',
                                  'Number of objects handled by the daemon (inspections)',
                                  ['type', 'name'])
        objects_moved_cold = Counter(f'{METRIC_PREFIX}objects_moved_cold', 'Number of objects moved to cold storage',
                                     ['type', 'name'])
        objects_moved_hot = Counter(f'{METRIC_PREFIX}objects_moved_hot', 'Number of objects moved to hot storage',
                                    ['type', 'name'])
        bitrate_threshold_exceeded = Counter(f'{METRIC_PREFIX}bitrate_threshold_exceeded',
                                             'Number of objects which were ignored due to too high or unknown bitrate',
                                             ['type', 'name'])
        for lib in libraries:
            library = plex.library.section(lib)
            if isinstance(library, MusicSection):
                handler = MusicHandler(config,
                                       library,
                                       init_time_metric.labels("Music", library.title),
                                       objects_handled.labels("Music", library.title),
                                       objects_moved_cold.labels("Music", library.title),
                                       objects_moved_hot.labels("Music", library.title),
                                       bitrate_threshold_exceeded.labels("Music", library.title),
                                       incremental_time_metric.labels("Music", library.title),
                                       )
                # Start the handler
                thread_pool.apply_async(func=handler.initialize())
        thread_pool.join()


if __name__ == "__main__":
    main()
