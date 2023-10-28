
import pygame
import sys
import random
from environment import Environment
from pygame.locals import *

def wait_for_space():
	while True:
		for event in pygame.event.get():
			if event.type == QUIT:
				pygame.quit()
				sys.exit()
			if event.type == KEYDOWN and event.key == K_SPACE:
				return



def main():

	WIDTH, HEIGHT = 200, 200
	WHITE = (255, 255, 255)
	SCALING_FACTOR = 3

	STEPS_PER_GENERATION = 150
	N_GENERATIONS = 10
	POPULATION = 100
	MUTATION_RATE = 0.05

	environment = Environment(WIDTH, HEIGHT, POPULATION, MUTATION_RATE)

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

				print(f'Generation {generation}')
				### Step Loop ###

				for step in range(STEPS_PER_GENERATION):

					# Get decisions from cells
					cells_arr = environment.get_cells()

					#print(cells_arr[0])

					for i in range(len(cells_arr)):

						# Get cells
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

					pygame.time.wait(1)
					win.blit(pygame.transform.scale(screen, win.get_rect().size), (0, 0))
					pygame.display.update()

				
				updating = False
				wait_for_space()
				updating = True
				environment.get_next_generation_asexually()





		win.blit(pygame.transform.scale(screen, win.get_rect().size), (0, 0))
		pygame.display.update()


	# Quit Pygame
	pygame.quit()
	sys.exit()



if __name__ == '__main__':
	main()