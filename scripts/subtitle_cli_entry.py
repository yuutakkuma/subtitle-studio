import multiprocessing


if __name__ == "__main__":
    multiprocessing.freeze_support()

    from subtitle import main

    main()
