#~
#~  Author:   C. Moller
#~  Date:     08 March 2011
#~  Updated:  10 January 2018
#~
#~  Description:  Arrange Unsorted Bank Statement CSV Files into Yearly Directories and Monthly Files
#~    Checks for and prevents duplicate entries
#~    NOTE: the source and output directory arguments must be relative to the current working directory of the OS
#~
#~  Usage:    python arrange_cli.py [sourcedir] [outputdir] [groupdir]
#~  Example:  python arrange_cli.py clean arranged wc
#~

import sys,os

#
# TRANSACTION CLASS
# Extract transaction properties from a CSV line string.
#
class Transaction:

  csvDelimiter = ','

  def __init__(self, csvLineStr):
    columns = csvLineStr.split(Transaction.csvDelimiter)
    self.id       = columns[0]
    self.date     = columns[1]
    self.desc     = columns[2]
    self.amount   = columns[3]
    self.balance  = columns[4]
    self.trxtype  = columns[5]
    self.year     = self.id[:4]
    self.month    = self.id[4:6]
    self.day      = self.id[6:8]
    self.asString = csvLineStr


#
# TRANSACTIONS FILE CLASS
# Open or create a bank transaction CSV file
# Convert CSV file content into a Transaction Objects List with TRXID keys
# Extends and sorts transaction objects
# Save transaction objects back to CSV
#
class TransactionsFile:

  def __init__(self, filePath, openLater = False):
    #print 'TransactionFile::init() - "%s"' % filePath
    self.filePath = filePath
    self.dirPath = os.path.dirname(self.filePath)
    self.titlesLineStr = ''
    self.items = {}
    if not openLater:
      self.open()

  def extendItems(self, extraItems):
    for trx in extraItems:
        self.items[trx.id] = trx # TRXID key prevents duplicates

  def createDirectoryPathIfRequired(self):
    if not os.path.exists(self.dirPath):
      try:
        os.makedirs(self.dirPath)
      except OSError as exc: # Guard against race condition
        if exc.errno != errno.EEXIST:
          raise
      print 'Create Directory:', self.dirPath

  def getItemsAsCsvLines(self, sortLinesByDate):
    lines = [self.titlesLineStr]
    itemKeysList = self.items.keys()
    if sortLinesByDate:
      itemKeysList.sort() # The TRXID key structure naturally sorts by date
    for key in itemKeysList:
      lines.append(self.items[key].asString)
    return lines

  def open(self):
    self.createDirectoryPathIfRequired()
    print 'Open:', self.filePath
    f = open(self.filePath, 'r')
    lines = f.readlines()
    self.titlesLineStr = lines.pop(0) # Assume we ALWAYS have a titles line.
    for csvLineStr in lines:
      trx = Transaction(csvLineStr)
      self.items[trx.id] = trx
    f.close()

  def save(self, sortByDate = True):
    self.createDirectoryPathIfRequired()
    f = open(self.filePath, 'w')
    f.writelines(self.getItemsAsCsvLines(sortByDate))
    f.close()


#
# YEAR-MONTH GROUP CLASS
# A container to store / group transaction objects with the same year and month
# Creates and updates a persistent CSV file store for this group
#
class YearMonthGroup:

  groupFileExt = '.csv'

  monthGroupNames = ('01_Jan', '02_Feb', '03_Mar', '04_Apr', '05_May', '06_Jun',
    '07_Jul', '08_Aug', '09_Sep', '10_Oct', '11_Nov', '12_Dec')

  def __init__(self, year, month):
    self.year = year
    self.month = month
    self.items = []
    self.groupFile = None # TypeOf: TransactionsFile

  def getOrCreateGroupFile(self, outputPath, titlesLineStr):
    groupFileName = self.monthGroupNames[int(self.month) - 1] + self.groupFileExt
    groupFilePath = os.path.join(outputPath, self.year, groupFileName)
    if os.path.isfile(groupFilePath):
      self.groupFile = TransactionsFile(groupFilePath)
    else:
      self.groupFile = TransactionsFile(groupFilePath, 'w')
    self.groupFile.titlesLineStr = titlesLineStr

  def mergeGroupItemsIntoGroupFileItems(self):
    self.groupFile.extendItems(self.items)

  def saveGroupFileItems(self):
    self.groupFile.save()


#
# TRANSACTION SET MODEL CLASS
# Reads a raw transactions CSV file and saves its content out into year-month-group CSV files
# Also prevents duplicate transactions and sorts group files by date
#
class TransactionSetModel:

  def __init__(self, sourceFilePath):
    self.sourceFile = TransactionsFile(sourceFilePath)
    self.yearMonthGroups = {}

  def groupTrxsByYearAndMonth(self):
    for trx in self.sourceFile.items.values():
      # If we don't already have the transaction's YEAR GROUP, create it
      if not (trx.year in self.yearMonthGroups):
        self.yearMonthGroups.setdefault(trx.year, {})
      # If we don't already have the transaction's MONTH SUB-GROUP, create it
      if not (trx.month in self.yearMonthGroups[trx.year]):
        self.yearMonthGroups[trx.year].setdefault(trx.month, YearMonthGroup(trx.year, trx.month))
      # Add the transaction to the MONTH SUB-GROUP
      self.yearMonthGroups[trx.year][trx.month].items.append(trx)

  def saveTrxsGroupsIntoGroupFiles(self, outputPath):
    for yearGroup in self.yearMonthGroups.values():
      for yearMonthGroup in yearGroup.values():
        yearMonthGroup.getOrCreateGroupFile(outputPath, self.sourceFile.titlesLineStr)
        yearMonthGroup.mergeGroupItemsIntoGroupFileItems()
        yearMonthGroup.saveGroupFileItems()


#
# TRANSACTIONS ARRANGER CLASS
# Process a directory of raw bank transaction CSV files. Group all the
# transactions found into year-month groups without duplicates and sorted by date.
# Save the year-month transaction groups into year-month-group CSV files.
#
class Arranger:

  def __init__(self, sourceDirectory, outputDirectory, groupDirectory = ''):
    if not len(outputDirectory):
      sys.exit('Arranger::init(), ERROR: The "outputDirectory" param MUST have a value!')
      return
    self.basePath = os.getcwd()
    self.groupDirectory = groupDirectory
    self.sourcePath = os.path.join(self.basePath, sourceDirectory, groupDirectory)
    self.outputPath = os.path.join(self.basePath, outputDirectory, groupDirectory)

  def createOutputDirectoryIfRequired(self):
    if not os.path.exists(self.outputPath):
      try:
        os.makedirs(self.outputPath)
      except OSError as exc: # Guard against race condition
        if exc.errno != errno.EEXIST:
          raise

  def rm_rf(self, f):
    if os.path.isfile(f):
      print 'Delete file:', f
      return os.unlink(f)
    if os.path.isdir(f):
      print 'Delete directory recursively:', f
      for path in (os.path.join(f, ff) for ff in os.listdir(f)):
        if os.path.isdir(path):
          rm_rf(path)
        else:
          os.unlink(path)
      return os.rmdir(f)
    raise TypeError, 'Arranger::rm_rf(), f parameter must be either a file or directory'

  def deleteOutputDirectoryContent(self):
    map(self.rm_rf, (os.path.join(self.outputPath, f) for f in os.listdir(self.outputPath)) )

  def fileIsCsv(self, filename):
    return not (filename.rfind('.csv') == -1)

  def arrange(self):
    for root, dirs, files in os.walk(self.sourcePath):
      for filename in files:
        if self.fileIsCsv(filename):
          print '---\nProcess file:', filename
          srcFilePath = os.path.join(root, filename)
          trxSetModel = TransactionSetModel(srcFilePath)
          trxSetModel.groupTrxsByYearAndMonth()
          trxSetModel.saveTrxsGroupsIntoGroupFiles(self.outputPath)


#
# MAIN
#
if __name__ == '__main__':

  if len(sys.argv) == 4: # The program name and the two arguments
    arranger = Arranger(sys.argv[1], sys.argv[2], sys.argv[3])
    print 'Arranger::Start - Source Path:', arranger.sourcePath
    print 'Arranger::Start - Output Path:', arranger.outputPath
    print 'Arranger::Start - Group Directory:', arranger.groupDirectory,
    arranger.createOutputDirectoryIfRequired()
    arranger.deleteOutputDirectoryContent()
    arranger.arrange()
    print 'Arranger::Done!\n'

  else: # Oops...
    errorMessage = 'Arranger Error: Incorrect argument count. Expected 2, got ' + str(len(sys.argv)-1) + '\n'
    errorMessage += 'Correct format: python arrange_cli.py [start_path] [dest_path]\n'
    errorMessage += 'Example:  python arrange_cli.py clean arranged wc\n\n'
    error_message += 'Output: {os.cwd}/{output_dir}/{group_dir}/{year}/{no}_{Month}.csv\n'
    error_message += 'Output Example: ./arranged/wc/01_Jan.csv'
    sys.exit(errorMessage)
