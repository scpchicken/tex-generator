i = 0;
while (i < argc) {
    len = argv_len(i);
    print(len)
    putc(10)

    # Loop over each character in argument 1 and output it
    j = 0;
    while (j < len) {
        ch = argv(i, j);
        println(ch);
        j = j + 1;
    }
    putc(10);
    putc(10);
    i = i + 1;
} 
