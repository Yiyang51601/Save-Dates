import sys

if "--web" in sys.argv:
    from save_dates.server import main as web_main

    web_main()
else:
    from save_dates.desktop import main

    main()
