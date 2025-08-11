import random
rand_list = [random.randint(1, 20) for v in range(10)]
list_comprehension_below_10 = [v for v in rand_list if v < 10]
list_filter_below_10 = list(filter(lambda num : num < 10, rand_list))