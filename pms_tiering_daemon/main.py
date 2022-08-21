from prometheus_client import start_http_server
import yaml
from plexapi.myplex import MyPlexAccount


def main():
    print("Loading configuration...")
    with open("config.yaml", "r") as yamlfile:
        config = yaml.load(yamlfile, Loader=yaml.FullLoader)
        print(f"Loaded config {config}")
        if config["enableMetrics"]:
            print("Enabling prometheus metrics")
            start_http_server(9090)
        print("Connecting to plex")
        account = MyPlexAccount(config["username"], config["password"])
        plex = account.resource(config["server"]).connect()
        for lib in config["libraries"]:
            library = plex.library.section(lib)
            if isinstance(library, MusicSection):
                # TODO timer for this operation
                # TODO refactor all this into a separate class
                # TODO schedule these as tasks in an executor with multiple threads
                tracks = library.searchTracks()




if __name__ == "__main__":
    main()
