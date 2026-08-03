a = 0
b = 1
i = 0
arr = []

while (i < 10) {
    arr[i] = a
    temp = a + b
    a = b
    b = temp
    i += 1
}

while (i > 0) {
    i -= 1
    println(arr[i])
}