Readme


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

