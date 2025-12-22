from multiprocessing import Pool
import time

def fib(n):
    if n < 2:
        return n
    return fib(n-1) + fib(n-2)

if __name__ == "__main__":
    for w in [1, 2, 4, 8]:
        start = time.time()
        with Pool(w) as p:
            p.map(fib, [35]*w)
        print(w, time.time() - start)
