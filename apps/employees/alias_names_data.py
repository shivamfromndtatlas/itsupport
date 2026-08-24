"""Curated lists of common US first/last names, grouped by starting letter.

Used to generate alias-name suggestions that share initials with an
employee's real name (see alias_rules.suggest_aliases). Coverage is
intentionally uneven -- some letters (Q, X, Z) have very few common
western names and are left sparse rather than padded with invented ones.
"""

FIRST_NAMES = {
    'A': ['Andrew', 'Adam', 'Anthony', 'Aaron', 'Alex', 'Amy', 'Alice', 'Amanda', 'Austin', 'Abigail'],
    'B': ['Benjamin', 'Brian', 'Brandon', 'Bruce', 'Bradley', 'Barbara', 'Brenda', 'Betty', 'Bryan', 'Blake'],
    'C': ['Charles', 'Christopher', 'Craig', 'Curtis', 'Carl', 'Catherine', 'Carol', 'Christine', 'Chad', 'Cody'],
    'D': ['David', 'Daniel', 'Douglas', 'Dennis', 'Derek', 'Diana', 'Donna', 'Debra', 'Dylan', 'Dustin'],
    'E': ['Edward', 'Eric', 'Ethan', 'Evan', 'Elijah', 'Elizabeth', 'Emily', 'Emma', 'Ella', 'Ellen'],
    'F': ['Frank', 'Frederick', 'Francis', 'Felix', 'Floyd', 'Frances', 'Faith', 'Fiona', 'Forrest', 'Finn'],
    'G': ['George', 'Gary', 'Gregory', 'Gerald', 'Gavin', 'Grace', 'Gloria', 'Gabrielle', 'Glenn', 'Garrett'],
    'H': ['Henry', 'Harold', 'Howard', 'Harry', 'Hunter', 'Helen', 'Heather', 'Holly', 'Hannah', 'Hailey'],
    'I': ['Ian', 'Isaac', 'Ivan', 'Isaiah', 'Irving', 'Irene', 'Isabel', 'Ingrid', 'Ivy', 'Iris'],
    'J': ['James', 'John', 'Joseph', 'Jason', 'Jeffrey', 'Jennifer', 'Jessica', 'Julia', 'Judith', 'Janet'],
    'K': ['Kevin', 'Keith', 'Kenneth', 'Kyle', 'Kurt', 'Karen', 'Kimberly', 'Katherine', 'Kelly', 'Kayla'],
    'L': ['Lawrence', 'Larry', 'Louis', 'Leonard', 'Logan', 'Laura', 'Linda', 'Lisa', 'Lauren', 'Lucy'],
    'M': ['Michael', 'Mark', 'Matthew', 'Martin', 'Marcus', 'Mary', 'Margaret', 'Michelle', 'Melissa', 'Megan'],
    'N': ['Nathan', 'Nicholas', 'Norman', 'Neil', 'Noah', 'Nancy', 'Nicole', 'Natalie', 'Nora', 'Naomi'],
    'O': ['Oliver', 'Oscar', 'Owen', 'Otis', 'Orson', 'Olivia', 'Ophelia', 'Odessa', 'Opal', 'Ora'],
    'P': ['Peter', 'Paul', 'Patrick', 'Philip', 'Preston', 'Patricia', 'Pamela', 'Paula', 'Penelope', 'Piper'],
    'Q': ['Quentin', 'Quincy', 'Quinn'],
    'R': ['Robert', 'Richard', 'Ronald', 'Raymond', 'Ryan', 'Ruth', 'Rachel', 'Rebecca', 'Rose', 'Renee'],
    'S': ['Steven', 'Scott', 'Stephen', 'Samuel', 'Shane', 'Susan', 'Sandra', 'Sarah', 'Stephanie', 'Sharon'],
    'T': ['Thomas', 'Timothy', 'Todd', 'Tyler', 'Trevor', 'Teresa', 'Tina', 'Tracy', 'Theresa', 'Tara'],
    'U': ['Ulysses', 'Upton'],
    'V': ['Victor', 'Vincent', 'Vernon', 'Virginia', 'Vanessa', 'Vicki', 'Valerie'],
    'W': ['William', 'Walter', 'Wayne', 'Warren', 'Wesley', 'Wanda', 'Whitney', 'Willa'],
    'X': ['Xavier'],
    'Y': ['Yale', 'Yvonne'],
    'Z': ['Zachary', 'Zane', 'Zoe'],
}

LAST_NAMES = {
    'A': ['Anderson', 'Allen', 'Adams', 'Armstrong', 'Austin', 'Alexander'],
    'B': ['Brown', 'Baker', 'Bennett', 'Bell', 'Bailey', 'Barnes', 'Bryant'],
    'C': ['Clark', 'Campbell', 'Carter', 'Collins', 'Cooper', 'Cook', 'Curtis'],
    'D': ['Davis', 'Diaz', 'Dixon', 'Douglas', 'Duncan', 'Dean'],
    'E': ['Evans', 'Edwards', 'Ellis', 'Elliott'],
    'F': ['Foster', 'Fisher', 'Ford', 'Freeman', 'Fox'],
    'G': ['Green', 'Gray', 'Gordon', 'Griffin', 'Gibson'],
    'H': ['Hall', 'Harris', 'Hill', 'Howard', 'Hughes', 'Henderson'],
    'I': ['Ingram', 'Irwin'],
    'J': ['Jones', 'Johnson', 'Jenkins', 'James'],
    'K': ['King', 'Kelly', 'Kennedy', 'Knight'],
    'L': ['Lewis', 'Long', 'Lawson', 'Lane'],
    'M': ['Miller', 'Moore', 'Martin', 'Mitchell', 'Morgan', 'Murphy'],
    'N': ['Nelson', 'Newman', 'Nash'],
    'O': ['Owens', 'Oliver', 'Ortiz'],
    'P': ['Parker', 'Patterson', 'Perry', 'Powell', 'Price'],
    'Q': ['Quinn'],
    'R': ['Reed', 'Reynolds', 'Rogers', 'Ross', 'Russell'],
    'S': ['Smith', 'Scott', 'Stewart', 'Stone', 'Simmons'],
    'T': ['Turner', 'Taylor', 'Thompson', 'Thomas'],
    'U': ['Underwood'],
    'V': ['Vance', 'Vaughn'],
    'W': ['White', 'Walker', 'Wood', 'Wells', 'Ward'],
    'X': [],
    'Y': ['Young'],
    'Z': ['Zimmerman'],
}
