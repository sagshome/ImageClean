Readme

from shell
python Utilities/build/build.py --force

Notes April 25/May 1st 2023
    We need to simplify this.
    System Folders
        self.duplicate_base = f'{self.app_name}_Duplicates'
        self.movies_base = f'{self.app_name}_ImageMovies'
        self.migration_base = f'{self.app_name}_Migrated'
        self.no_date_base = f'{self.app_name}_NoDate'
        self.small_base = f'{self.app_name}_Small'

    Step 1 do the import
        Use Case 1)
            Input Folder on a different path then Output Folder.   Normal mode,  try and move all files/folders - Use Case 9*
        Use Case 2)
            Input Folder == Output Folder - rerun
        Use Case 3)
            Input Folder == Child of Output Folder - Same as Use Case 1 but bear in mind we may try and import in place
        Use Case 4)
            Input Folder == Parent of Output Folder:
                We need to skip the child folder == Output Folder
        Use Case 5)
            Small file filter - My image storage quagmire includes thumbnails - support moving these to separate path

        Use Case 7)
            When importing a non image file,  just ignore it - if verbose then squawk
        Use Case 8)
            If the image is actually a movie,   move it to the Movie folder
        Use Case 9)
            Support for Import paths
            Use Case 9a)
                All imported files,  will start with a YEAR, or No_date folder
            Use Case 9b)
                If the import path has a description or descriptions then will be sub-folders after the year
                Use Case 9b-1)
                    If the imported folder,  has a dated path and a description,  use that date over any image date.
            Use Case 9c)
                If the import path does not have a description,  files are stored in YYYY/MM/DD  1961/09/04

        Use Case 6)
            Check for duplicates Output path (use case 9)
            Use Case 6a)
                This is a new file - move it to output path + register
            Use Case 6b)  - This is not a new file
                Use Case 6b-1 - This is a unique file
                    Use Case 6b-1a - The output path exists
                        Roll it over to name(n).type + register ?
                    Use Case 6b-1a - The output path does not exist
                        move to output path
                Use Case 6b-2 - This is a duplicate
                    Use Case 6b-2a - If output folder is better than exists
                        move to output path
                        move existing to duplicate path
                    Use Case 6b-2b - If output folder is worse than exists
                        move to duplicate path
                    Use Case 6b-2c - If they are the same score
                        move to output path  <- Issue here is I can have n copies of the same file Do I need to register them all ?

            Use Case 6b)
                If the files are not image identical

        a) If input and output folders are the same - nothing to do
        b) If using small filter and not small
            Move to YYYY/<description-less dates>
                 or
                    YYYY/MMM/DD
                - if the file exists use duplicate importing rules

                what if I had
                    foobar/pict-2003
                    foobar/pict-2010
                    foobar/pict-no_date

                Then...
                    2003/foobar/pict-2003
                    2010/foobar/pict-2010
                    No_date/foobar/pict-no_date

                what if I had
                    2004_foobar/pict-2003
                    2004_foobar/pict-2010
                    2004_foobar/pict-no_date

                Then...
                    2004/foobar/pict-2003
                                pict-2010
                                pict-no_date

                what if I had
                    2004/pict-2003
                    2004/pict-2010
                    2004/pict-no_date

                Then...
                    2003/pict-2003
                    2010/pict-2010
                    2004/pict-no_date


        Basically imports do Use folder dates when we got a description else use picture date unless we don't have one

        c) if using small filter and small
            Move to Small_files

    Step 2 if conversions required
        a) for every conversion filetype in output folders
            convert the file


    Step 3 refactor
        Process any new... No_Date files
        set date/time on photos (if not set)
        Process any Duplicates (if requested)


    Step 4 Audits
        Remove any empty folders
        Warn about any large folders

https://github.com/roseeng/photoarchive - Normalizing filenames
    Name comparison
    The logic for "similar names" are as follows:

    If file suffix is different, the files are different. Else remove suffix from comparison.
    Take the first 5 chars
    From the remainder, remove all digits
    From the result, remove underscores and parenthesis.
    The aim is to make files like "DSC4711.jpg" and "DSC4711(1).jpg" similar, but "47122.jpg" and "47123.jpg"
    different. In a future version, this should be tweakable. It is not the end of the world if it's not perfect
    though, the result is just more fstat() calls and hash calculations.

Equality (==)
    if Names are the same (above),  us file specific logic
    FileType specific logic
    - Images,   read the photo data and compare the histograms
    - Text, use a cmp function
    - Directories (TBD)

