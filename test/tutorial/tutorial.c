println("Hello, World!")

i = 0
while i < 10 {
    println(i)
    i += 1
}

i = 0
while i < argc {
    j = 0
    len = arglen(i)
    while j < len {
        c = argv(i, j)
        putc(c)
        j += 1
    }
    print("\n")
    i += 1
}