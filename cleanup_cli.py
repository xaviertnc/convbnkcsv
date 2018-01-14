#~
#~  Author:   C. Moller
#~  Date:     08 March 2011
#~  Updated:  10 January 2018
#~
#~  Description:  Change source CSV filenames to a common system that makes it easier to tell what
#~    date range each file represents. Also remove unnecessary white space and characters from
#~    transaction descriptions to reduce the overall description field length, saving disk space
#~    and making reports easier to read.
#~
#~  Usage:    python cleanup_cli.py [srcdir] [outputdir] [result_file_prefix]
#~  Example:  python cleanup_cli.py raw clean chk
#~
#~  NOTE: All paths/dirs are relative to the current working directory of the OS/file
#~  NOTE: Any sub-directories under the source directory will also be processed.
#~
#~  Raw files must be *.csv and can be ';' or ',' delimited
#~  Raw files must contain column titles as a first row.
#~  Raw files sould have the following format:
#~
#~     Date,Description,Amount,Balance
#~     20160831,"TRANSFER FROM    SOUTHDOWNS CARD NO. 7271 92-0436-2271 SONJA",20000,19048.98
#~
#~
#~  Result:   {destdir}/{prefix}_{fromdate}_{todate}.csv
#~  Example:  clean/chk/chk_20160401_20160908.csv
#~
#~     TrxId,Date,Description,Amount,Balance,Type
#~     201608311SONJA00200000+019048981,2016-08-31,TRANSFER SOUTHDOWNS 7271 92-0436-2271 SONJA,20000,19048.98,1
#~

import sys,os,re

#
# TRANSACTION CLASS
# Extract transaction properties from a CSV line string.
# Clean and/or transform existing transaction properties
# Add new transaction properties (e.g. TrxId, TrxType)
#
class Transaction:

  def __init__(self, index, csvLineStr, csvDelimiter):
    columns = csvLineStr.strip().split(csvDelimiter)
    self.id        = ''
    selfindex      = index
    self.date      = columns[0]
    self.desc      = columns[1]
    self.amount    = columns[2]
    self.balance   = columns[3]
    self.trxType   = ''
    self.day       = ''
    self.month     = ''
    self.year      = ''
    self.mySqlDate = ''
    self.idFragments = {}
    self.csvLineStr = csvLineStr
    self.csvDelimiter = csvDelimiter

  def truncate23DigitCardNumber(self, descStr):
    parts = descStr.split(' ')
    lastPartIndex = len(parts) - 1
    lastPart = parts[lastPartIndex]
    if len(lastPart) == 23 and lastPart.isdigit():
      parts[lastPartIndex] = lastPart[18:]
      return ' '.join(parts)
    return descStr

  def processDate(self):
      try:
        dateAsInt = int(self.date)
      except:
        dateAsInt = 0
      if not(dateAsInt) or len(self.date) != 8: # Validate date format
        print 'Trx[%d].date format is invalid. Trx.date: "%s"! Skip File' % (self.index, self.date)
        return False
      self.day = self.date[6:8]
      self.month = self.date[4:6]
      self.year = self.date[:4]
      self.mySqlDate = self.year + '-' + self.month + '-' + self.day
      self.idFragments['date'] = self.date
      self.date = dateAsInt

  def processDesc(self):
    s = self.desc
    s = re.sub('[^A-Za-z0-9/*\-_+&#:| ]+', '', s)
    s = s.replace(self.csvDelimiter, ' ')
    s = s.replace(' FROM', '')
    s = s.replace(' TO', '')
    s = s.replace('ABSA BANK', '')
    s = s.replace('IBANK', '')
    s = s.replace('ACB', '')
    s = s.replace('PURCHASE', '')
    s = s.replace('NOTIFIC FEE', '')
    s = s.replace(':EXTERNAL', '')
    s = s.replace('DEPOSIT', '')
    s = s.replace('CASH DEP', 'CASH')
    s = s.replace('SMS KENNISGEWINGS', '')
    s = s.replace('CARD NO', '')
    s = re.sub('\s\s+', ' ', s)
    s = self.truncate23DigitCardNumber(s)
    self.desc = s.strip()
    idFragment = re.sub('\s+', '', self.desc)
    if len(idFragment) <= 6:
      self.idFragments['desc'] = idFragment.zfill(6)
    else:
      self.idFragments['desc'] = idFragment[-6:]

  def processAmount(self):
    amount = float(self.amount)
    self.trxType = 1 if amount >= 0 else 2
    idFragment = str(abs(amount)).replace('.', '')
    self.idFragments['amount'] = idFragment.zfill(8)

  def processBalance(self):
    balance = float(self.balance)
    idFragment = str(abs(balance)).replace('.', '')
    self.idFragments['balance'] = ('+' if balance >= 0 else '-') + idFragment.zfill(8)

  def getTrxId(self):
    f = self.idFragments
    return f['date'] + f['desc'] + f['amount'] + f['balance'] + str(self.trxType)

  def toString(self):
    columns = (self.getTrxId(), self.mySqlDate, self.desc, self.amount, self.balance, str(self.trxType) )
    return self.csvDelimiter.join(columns) + '\n' # \n -or- os.linesep ?

#
# TRANSACTIONS FILE CLASS
# Open a transactions CSV file
# Convert transactions file CSV content into a Transaction Objects List
# Save transaction objects list back to CSV
#
class TransactionsFile:

  def __init__(self):
    self.items = [] # list of trx objects
    self.csvLines = [] # list of strings
    self.titlesLineStr = ''
    self.csvDelimiter = ','
    self.filePath = ''
    self.dirPath = ''

  def setFilePath(self, filePath):
    self.filePath = filePath
    self.dirPath = os.path.dirname(self.filePath)

  def createDirectoryPathIfRequired(self):
    if not os.path.exists(self.dirPath):
      try:
        os.makedirs(self.dirPath)
      except OSError as exc: # Guard against race condition
        if exc.errno != errno.EEXIST:
          raise
      print 'Create Directory:', self.dirPath

  def validateCsvLines(self):
    if len(self.csvLines) <= 1:
      print 'Error - CSV file empty or invalid - Skip File'
      return False
    firstLine = self.csvLines[0]
    if ';' in firstLine:
      print 'CSV delimiter = Semicolon (;)'
      delimiter = ';'
    elif ',' in firstLine:
      print 'CSV delimiter = Comma (,)'
      delimiter = ','
    else:
      print 'Error - Unable to detect CSV delimiter type - Skip File'
      return False
    if firstLine.strip() != 'Date' + delimiter + 'Description' + delimiter + 'Amount' + delimiter + 'Balance':
      print 'Error - CSV titles row missing or invalid - Skip File'
      return False
    self.csvDelimiter = delimiter
    self.titlesLineStr = firstLine
    return True

  def exportTrxObjectsAsCsvLines(self):
    csvLines = [self.titlesLineStr]
    for trx in self.items: csvLines.append(trx.toString())
    return csvLines

  def convertCsvLinesToTrxObjects(self):
    self.csvLines.pop(0) # Drop the titles line
    index = 0
    for csvLineStr in self.csvLines:
      trx = Transaction(index, csvLineStr, self.csvDelimiter)
      self.items.append(trx)
      index += 1

  def open(self, filePath):
    self.setFilePath(filePath)
    f = open(self.filePath, 'r')
    self.csvLines = f.readlines()
    f.close()

  def save(self):
    self.createDirectoryPathIfRequired()
    print 'SaveAs:', self.filePath
    f = open(self.filePath, 'w')
    f.writelines(self.exportTrxObjectsAsCsvLines())
    f.close()


#
# TRANSACTION SET MODEL CLASS
# Reads raw transaction CSV files and converts them to "cleaned" transaction CSV files
# Changes misc source filenames to a common filename format: {prefix}_{mindate}_{maxdate}.csv
#
class TransactionSetModel:

  def __init__(self, sourceFilePath, resultsFilenamePrefix, outputPath):
    self.sourceFile = TransactionsFile()
    self.resultsFile = TransactionsFile()
    self.sourceFile.open(sourceFilePath)
    self.resultsFilenamePrefix = resultsFilenamePrefix
    self.outputPath = outputPath

  def validateTransactionsSourceFile(self):
    return self.sourceFile.validateCsvLines()

  def convertCsvDataIntoTransactionObjects(self):
    self.sourceFile.convertCsvLinesToTrxObjects()

  def processAllTransactionObjects(self):
    for trx in self.sourceFile.items:
      trx.processDate()
      trx.processDesc()
      trx.processAmount()
      trx.processBalance()

  def getResultsFilename(self):
    firstTrx = self.sourceFile.items[0]
    minDate = firstTrx.date
    maxDate = minDate
    for trx in self.sourceFile.items:
      if trx.date < minDate: minDate = trx.date
      if trx.date > maxDate: maxDate = trx.date
    return '%s_%s_%s.csv' % (self.resultsFilenamePrefix, str(minDate), str(maxDate))

  def saveCleanedTransactionsToFile(self):
    self.resultsFile.items = self.sourceFile.items
    self.resultsFile.titlesLineStr = self.sourceFile.csvDelimiter.join(('TrxId', self.sourceFile.titlesLineStr.strip(), 'Type')) + '\n'
    self.resultsFile.setFilePath(os.path.join(self.outputPath, self.getResultsFilename()))
    self.resultsFile.save()


#
# TRANSACTION FILES CLEANER CLASS
# Process a directory of raw transaction CSV files.
# Clean each transaction in every file inside the source directory
# Save the cleaned transactions to a new set of clean CSV files.
#
class Cleaner:

  def __init__(self, sourceDirectory, outputDirectory, resultsFilenamePrefix):
    if not len(outputDirectory):
      sys.exit('Cleaner::init(), ERROR: The "Output Directory" param MUST have a value!')
      return
    self.basePath = os.getcwd()
    self.sourcePath = os.path.join(self.basePath, sourceDirectory, resultsFilenamePrefix)
    self.outputPath = os.path.join(self.basePath, outputDirectory, resultsFilenamePrefix)
    print 'Cleaner::Start - Source Path:', self.sourcePath
    print 'Cleaner::Start - Output Path:', self.outputPath
    print 'Cleaner::Start - Output Results Filename Prefix:', resultsFilenamePrefix
    self.resultsFilenamePrefix = resultsFilenamePrefix
    self.fileCount = 0

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
    raise TypeError, 'Cleaner::rm_rf(), f parameter must be either a file or directory'

  def deleteOutputDirectoryContent(self):
    map(self.rm_rf, (os.path.join(self.outputPath, f) for f in os.listdir(self.outputPath)) )

  def fileIsCsv(self, filename):
    return not (filename.rfind('.csv') == -1)

  def cleanup(self):
    for root, dirs, files in os.walk(self.sourcePath):
      for filename in files:
        if self.fileIsCsv(filename):
          self.fileCount += 1
          srcFilePath = os.path.join(root, filename)
          print '---\nClean file #%d: %s' % (self.fileCount, srcFilePath)
          trxSetModel = TransactionSetModel(srcFilePath, self.resultsFilenamePrefix, self.outputPath)
          if not trxSetModel.validateTransactionsSourceFile(): continue
          trxSetModel.convertCsvDataIntoTransactionObjects()
          trxSetModel.processAllTransactionObjects()
          trxSetModel.saveCleanedTransactionsToFile()
    print '\nCleaner::Done!\n'

#
# MAIN
#
if __name__ == '__main__':

  if len(sys.argv) == 4: # The program name and the two arguments
    cleaner = Cleaner(sys.argv[1], sys.argv[2], sys.argv[3])
    cleaner.createOutputDirectoryIfRequired()
    cleaner.deleteOutputDirectoryContent()
    cleaner.cleanup()

  else: # Oops...
    error_message = 'Cleaner Error: Incorrect argument count. Expected 4, got ' + str(len(sys.argv)-1) + '\n'
    error_message += 'Correct format: python cleanup_cli.py [source directory] [output directory] [output prefix]\n'
    error_message += 'Example: python cleanup_cli.py raw clean chk\n\n'
    error_message += 'Output: {os.cwd}/{output_dir}/{prefix}/{prefix}_{mindate}_{maxdate}.csv\n'
    error_message += 'Output Example: ./clean/chk/chk_20160401_20160908.csv'
    sys.exit(error_message)
