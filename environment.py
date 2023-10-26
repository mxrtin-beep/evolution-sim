
import random
from cell import Cell

n_genes = 4
n_inner_neurons = 2

class Environment:

	def __init__(self, x_size, y_size, population, steps_per_gen, n_generations):

		self.x_size = x_size
		self.y_size = y_size
		self.population = population
		self.steps_per_gen = steps_per_gen


		self.cells = []

		for i in range(population):
			x_i = random.randint(0, self.x_size)
			y_i = random.randint(0, self.y_size)

			self.cells.append(Cell(x_i, y_i, n_genes, n_inner_neurons, i))


		self.grid = []

	def get_cells(self):
		return self.cells