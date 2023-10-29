
import pygame
import sys
import random
from environment import Environment
from pygame.locals import *
import matplotlib.pyplot as plt
import os

def wait_for_space():
	while True:
		for event in pygame.event.get():
			if event.type == QUIT:
				pygame.quit()
				sys.exit()
			if event.type == KEYDOWN and event.key == K_SPACE:
				return



def main():

	os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (0,0)

	WIDTH, HEIGHT = 200, 200
	WHITE = (255, 255, 255)
	SCALING_FACTOR = 3

	STEPS_PER_GENERATION = 200
	N_GENERATIONS = 1000
	POPULATION = 100
	MUTATION_RATE = 0.00
	N_PARENTS = 2

	# Statistics
	survival_rate_stat = []
	genetic_diversity_stat = []

	environment = Environment(WIDTH, HEIGHT, POPULATION, MUTATION_RATE)

	NEW_POPULATION = POPULATION


	pygame.init()

	screen = pygame.display.set_mode((WIDTH, HEIGHT))
	pygame.display.set_caption("Evolution")
	win = pygame.display.set_mode((WIDTH*SCALING_FACTOR, HEIGHT*SCALING_FACTOR))

	screen = pygame.Surface((WIDTH, HEIGHT))


	running = True
	updating = True

	while running:
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				running = False

		screen.fill(WHITE)


		# Draw Cells
		cells_arr = environment.get_cells()
		for cell in cells_arr:
			screen.set_at((cell.get_x(), cell.get_y()), cell.get_color())

		### Generational Loop ###

		while updating:
			for generation in range(N_GENERATIONS):

				print(f'Generation {generation+1}')
				### Step Loop ###


				for step in range(STEPS_PER_GENERATION):

					# Get decisions from cells
					cells_arr = environment.get_cells()

					for i in range(len(cells_arr)):

						# Get cell
						cell = cells_arr[i]

						# Update Sensory Neurons
						cell.activate_sensory_neurons()
						cell.think()

						# Execute decision
						decision_list = cell.execute_decision()
						
						# Grow
						cell.age_up()



					# Update board
					screen.fill(WHITE)
					for cell in cells_arr:
						screen.set_at((cell.get_x(), cell.get_y()), cell.get_color())

					#pygame.time.wait(3)
					win.blit(pygame.transform.scale(screen, win.get_rect().size), (0, 0))
					pygame.display.update()

					### Step Loop ###
				
				#updating = False
				#wait_for_space()
				#updating = True
				genetic_diversity = environment.calculate_genetic_diversity()
				genetic_diversity_stat.append(genetic_diversity)

				survival_rate = environment.enact_selection_pressure()
				survival_rate_stat.append(survival_rate)
				if survival_rate == 0:
					print('Everyone Died!')
					updating = False
					running = False
					quit()
				else:
					environment.get_next_generation(n_parents=N_PARENTS, new_population=NEW_POPULATION)
				plt.plot(survival_rate_stat, label='Percent Surviving', color='red')
				plt.plot(genetic_diversity_stat, label='Genetic Diversity', color='blue')
				plt.xlabel('Generation')
				if generation == 0:
					plt.legend()
				plt.savefig('stats.png')

				
				print(f'Genetic Diversity: {round(genetic_diversity, 2)}%, Survival Rate: {round(survival_rate, 2)}%.')
				### Generation Loop ###

			updating = False

			### Updating Loop ###


		win.blit(pygame.transform.scale(screen, win.get_rect().size), (0, 0))
		pygame.display.update()


	# Quit Pygame
	pygame.quit()
	sys.exit()

	plt.savefig('percent_surviving.png')



if __name__ == '__main__':
	main()